"""
HTML template renderer for StreamOps overlays.
Renders overlay templates with dynamic content and styling.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from datetime import datetime, timedelta
import json
import uuid

from app.api.schemas.overlays import OverlayType, OverlayResponse

logger = logging.getLogger(__name__)


class OverlayRenderer:
    """Renders overlay templates with dynamic content."""
    
    def __init__(self, template_dir: Optional[Path] = None):
        # Set default template directory
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = template_dir
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters and functions
        self._setup_template_functions()
        
        # Cache for compiled templates
        self._template_cache: Dict[str, Template] = {}
    
    def _setup_template_functions(self):
        """Setup custom Jinja2 filters and functions."""
        
        def format_duration(seconds: int) -> str:
            """Format duration in seconds to HH:MM:SS."""
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        def time_ago(timestamp: datetime) -> str:
            """Format timestamp as time ago string."""
            now = datetime.utcnow()
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            diff = now - timestamp
            
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                return "just now"
        
        def truncate_words(text: str, count: int = 10) -> str:
            """Truncate text to specified word count."""
            words = text.split()
            if len(words) <= count:
                return text
            return ' '.join(words[:count]) + '...'
        
        def generate_uuid():
            """Generate a UUID4 string."""
            return str(uuid.uuid4())
        
        def now():
            """Get current UTC timestamp."""
            return datetime.utcnow()
        
        def format_number(num: int) -> str:
            """Format number with commas."""
            return f"{num:,}"
        
        # Register filters
        self.env.filters['format_duration'] = format_duration
        self.env.filters['time_ago'] = time_ago
        self.env.filters['truncate_words'] = truncate_words
        
        # Register globals
        self.env.globals['uuid4'] = generate_uuid
        self.env.globals['now'] = now
        self.env.globals['format_number'] = format_number
    
    def get_template(self, template_name: str) -> Template:
        """Get and cache a template."""
        if template_name not in self._template_cache:
            try:
                self._template_cache[template_name] = self.env.get_template(template_name)
            except Exception as e:
                logger.error(f"Failed to load template {template_name}: {e}")
                raise
        
        return self._template_cache[template_name]
    
    def render_overlay(
        self, 
        overlay: OverlayResponse, 
        extra_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Render an overlay to HTML, CSS, and JS.
        
        Args:
            overlay: Overlay configuration
            extra_context: Additional template variables
            
        Returns:
            Dict containing 'html', 'css', and 'js' strings
        """
        try:
            # Determine template based on overlay type
            template_name = self._get_template_name(overlay.overlay_type)
            
            # Prepare template context
            context = {
                'overlay': overlay,
                'overlay_id': overlay.id,
                'overlay_type': overlay.overlay_type.value,
                'content': overlay.content,
                'style': overlay.style,
                'position': overlay.position,
                'timestamp': datetime.utcnow().isoformat(),
                **(extra_context or {})
            }
            
            # Render main template
            template = self.get_template(template_name)
            html = template.render(**context)
            
            # Generate CSS
            css = self._generate_css(overlay, context)
            
            # Generate JavaScript
            js = self._generate_js(overlay, context)
            
            return {
                'html': html,
                'css': css,
                'js': js
            }
            
        except Exception as e:
            logger.error(f"Failed to render overlay {overlay.id}: {e}")
            return self._render_error_overlay(str(e))
    
    def render_overlay_page(
        self, 
        overlay: OverlayResponse, 
        websocket_url: str = "ws://localhost:7769/overlay/ws",
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a complete HTML page for an overlay browser source.
        
        Args:
            overlay: Overlay configuration
            websocket_url: WebSocket URL for real-time updates
            extra_context: Additional template variables
            
        Returns:
            Complete HTML page as string
        """
        try:
            # Render overlay components
            rendered = self.render_overlay(overlay, extra_context)
            
            # Use base template for complete page
            base_template = self.get_template('base.html')
            
            page_html = base_template.render(
                overlay=overlay,
                overlay_id=overlay.id,
                overlay_html=rendered['html'],
                overlay_css=rendered['css'],
                overlay_js=rendered['js'],
                websocket_url=websocket_url,
                page_title=f"StreamOps Overlay - {overlay.name}",
                **(extra_context or {})
            )
            
            return page_html
            
        except Exception as e:
            logger.error(f"Failed to render overlay page {overlay.id}: {e}")
            return self._render_error_page(str(e))
    
    def render_multiple_overlays(
        self, 
        overlays: List[OverlayResponse],
        websocket_url: str = "ws://localhost:7769/overlay/ws",
        scene: Optional[str] = None
    ) -> str:
        """
        Render multiple overlays in a single page for scene-based display.
        
        Args:
            overlays: List of overlay configurations
            websocket_url: WebSocket URL for real-time updates
            scene: Scene name for filtering
            
        Returns:
            Complete HTML page with multiple overlays
        """
        try:
            # Filter overlays for scene if specified
            if scene:
                overlays = [
                    o for o in overlays 
                    if not o.scene_filter or scene in o.scene_filter
                ]
            
            # Render each overlay
            rendered_overlays = []
            all_css = []
            all_js = []
            
            for overlay in overlays:
                rendered = self.render_overlay(overlay)
                rendered_overlays.append({
                    'overlay': overlay,
                    'html': rendered['html'],
                    'visible': overlay.enabled
                })
                all_css.append(rendered['css'])
                all_js.append(rendered['js'])
            
            # Use multi-overlay template
            template = self.get_template('multi_overlay.html')
            
            page_html = template.render(
                overlays=rendered_overlays,
                combined_css='\n\n'.join(all_css),
                combined_js='\n\n'.join(all_js),
                websocket_url=websocket_url,
                scene=scene,
                page_title=f"StreamOps Overlays{' - ' + scene if scene else ''}",
                overlay_count=len(rendered_overlays)
            )
            
            return page_html
            
        except Exception as e:
            logger.error(f"Failed to render multiple overlays: {e}")
            return self._render_error_page(str(e))
    
    def _get_template_name(self, overlay_type: OverlayType) -> str:
        """Get template filename for overlay type."""
        template_map = {
            OverlayType.text: 'text.html',
            OverlayType.image: 'image.html',
            OverlayType.video: 'video.html',
            OverlayType.html: 'custom.html',
            OverlayType.countdown: 'countdown.html',
            OverlayType.progress_bar: 'progress_bar.html',
            OverlayType.recent_follower: 'recent_follower.html',
            OverlayType.scene_info: 'scene_info.html',
            OverlayType.chat_display: 'chat_display.html'
        }
        
        return template_map.get(overlay_type, 'text.html')
    
    def _generate_css(self, overlay: OverlayResponse, context: Dict[str, Any]) -> str:
        """Generate CSS for overlay based on style configuration."""
        css_parts = []
        
        # Base overlay styles
        css_parts.append(f"""
        #{overlay.id} {{
            position: absolute;
            left: {overlay.position.x}px;
            top: {overlay.position.y}px;
            z-index: {overlay.position.z_index};
        """)
        
        if overlay.position.width:
            css_parts.append(f"width: {overlay.position.width}px;")
        if overlay.position.height:
            css_parts.append(f"height: {overlay.position.height}px;")
        
        # Style-based CSS
        style = overlay.style
        if style.background_color:
            css_parts.append(f"background-color: {style.background_color};")
        if style.text_color:
            css_parts.append(f"color: {style.text_color};")
        if style.font_family:
            css_parts.append(f"font-family: {style.font_family};")
        if style.font_size:
            css_parts.append(f"font-size: {style.font_size};")
        if style.opacity is not None:
            css_parts.append(f"opacity: {style.opacity};")
        if style.border_radius:
            css_parts.append(f"border-radius: {style.border_radius};")
        if style.padding:
            css_parts.append(f"padding: {style.padding};")
        if style.margin:
            css_parts.append(f"margin: {style.margin};")
        
        css_parts.append("}")
        
        # Animation classes
        css_parts.extend([
            """
            /* Animation classes */
            .overlay-hidden { opacity: 0; transform: scale(0.8); }
            .overlay-visible { opacity: 1; transform: scale(1); }
            
            .fade-in { animation: fadeIn 0.5s ease-in-out forwards; }
            .fade-out { animation: fadeOut 0.5s ease-in-out forwards; }
            .slide-in-right { animation: slideInRight 0.5s ease-out forwards; }
            .slide-in-left { animation: slideInLeft 0.5s ease-out forwards; }
            .slide-in-up { animation: slideInUp 0.5s ease-out forwards; }
            .slide-in-down { animation: slideInDown 0.5s ease-out forwards; }
            .zoom-in { animation: zoomIn 0.3s ease-out forwards; }
            .zoom-out { animation: zoomOut 0.3s ease-out forwards; }
            .bounce-in { animation: bounceIn 0.6s ease-out forwards; }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
            
            @keyframes slideInRight {
                from { transform: translateX(100px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            @keyframes slideInLeft {
                from { transform: translateX(-100px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            @keyframes slideInUp {
                from { transform: translateY(50px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            
            @keyframes slideInDown {
                from { transform: translateY(-50px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            
            @keyframes zoomIn {
                from { transform: scale(0.3); opacity: 0; }
                to { transform: scale(1); opacity: 1; }
            }
            
            @keyframes zoomOut {
                from { transform: scale(1); opacity: 1; }
                to { transform: scale(0.3); opacity: 0; }
            }
            
            @keyframes bounceIn {
                0% { transform: scale(0.3); opacity: 0; }
                50% { transform: scale(1.05); }
                70% { transform: scale(0.9); }
                100% { transform: scale(1); opacity: 1; }
            }
            """
        ])
        
        return '\n'.join(css_parts)
    
    def _generate_js(self, overlay: OverlayResponse, context: Dict[str, Any]) -> str:
        """Generate JavaScript for overlay interactivity."""
        js_parts = []
        
        # Base overlay JavaScript
        js_parts.append(f"""
        // Overlay {overlay.id} JavaScript
        (function() {{
            const overlayElement = document.getElementById('{overlay.id}');
            if (!overlayElement) return;
            
            // Animation utilities
            function animate(element, animationClass, callback) {{
                element.classList.add(animationClass);
                const animationEnd = () => {{
                    element.classList.remove(animationClass);
                    element.removeEventListener('animationend', animationEnd);
                    if (callback) callback();
                }};
                element.addEventListener('animationend', animationEnd);
            }}
            
            // Show overlay with animation
            function showOverlay(animationType = 'fade-in') {{
                overlayElement.style.display = 'block';
                overlayElement.classList.remove('overlay-hidden');
                overlayElement.classList.add('overlay-visible');
                animate(overlayElement, animationType);
            }}
            
            // Hide overlay with animation
            function hideOverlay(animationType = 'fade-out', callback) {{
                animate(overlayElement, animationType, () => {{
                    overlayElement.style.display = 'none';
                    overlayElement.classList.remove('overlay-visible');
                    overlayElement.classList.add('overlay-hidden');
                    if (callback) callback();
                }});
            }}
            
            // Update overlay content
            function updateContent(content) {{
                if (content.text) {{
                    const textElements = overlayElement.querySelectorAll('.overlay-text');
                    textElements.forEach(el => el.textContent = content.text);
                }}
                
                if (content.image_url) {{
                    const imgElements = overlayElement.querySelectorAll('.overlay-image');
                    imgElements.forEach(el => el.src = content.image_url);
                }}
                
                if (content.html) {{
                    const htmlElements = overlayElement.querySelectorAll('.overlay-content');
                    htmlElements.forEach(el => el.innerHTML = content.html);
                }}
                
                // Update template variables
                if (content.template_variables) {{
                    for (const [key, value] of Object.entries(content.template_variables)) {{
                        const elements = overlayElement.querySelectorAll(`[data-variable="${{key}}"]`);
                        elements.forEach(el => {{
                            if (el.tagName === 'IMG') {{
                                el.src = value;
                            }} else {{
                                el.textContent = value;
                            }}
                        }});
                    }}
                }}
            }}
            
            // Expose functions globally for WebSocket control
            window.overlay_{overlay.id.replace('-', '_')} = {{
                show: showOverlay,
                hide: hideOverlay,
                update: updateContent,
                element: overlayElement
            }};
        }})();
        """)
        
        # Type-specific JavaScript
        if overlay.overlay_type == OverlayType.countdown:
            js_parts.append(self._generate_countdown_js(overlay))
        elif overlay.overlay_type == OverlayType.progress_bar:
            js_parts.append(self._generate_progress_js(overlay))
        
        return '\n'.join(js_parts)
    
    def _generate_countdown_js(self, overlay: OverlayResponse) -> str:
        """Generate JavaScript for countdown overlay."""
        return f"""
        // Countdown functionality for {overlay.id}
        (function() {{
            const countdownElement = document.getElementById('{overlay.id}').querySelector('.countdown-display');
            if (!countdownElement) return;
            
            let countdownInterval;
            
            function startCountdown(targetTime) {{
                if (countdownInterval) clearInterval(countdownInterval);
                
                countdownInterval = setInterval(() => {{
                    const now = new Date().getTime();
                    const distance = new Date(targetTime).getTime() - now;
                    
                    if (distance < 0) {{
                        countdownElement.textContent = "00:00:00";
                        clearInterval(countdownInterval);
                        return;
                    }}
                    
                    const hours = Math.floor(distance / (1000 * 60 * 60));
                    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                    
                    countdownElement.textContent = 
                        String(hours).padStart(2, '0') + ':' +
                        String(minutes).padStart(2, '0') + ':' +
                        String(seconds).padStart(2, '0');
                }}, 1000);
            }}
            
            // Expose countdown control
            if (window.overlay_{overlay.id.replace('-', '_')}) {{
                window.overlay_{overlay.id.replace('-', '_')}.startCountdown = startCountdown;
            }}
        }})();
        """
    
    def _generate_progress_js(self, overlay: OverlayResponse) -> str:
        """Generate JavaScript for progress bar overlay."""
        return f"""
        // Progress bar functionality for {overlay.id}
        (function() {{
            const progressBar = document.getElementById('{overlay.id}').querySelector('.progress-bar');
            const progressFill = progressBar?.querySelector('.progress-fill');
            const progressText = progressBar?.querySelector('.progress-text');
            
            if (!progressBar || !progressFill) return;
            
            function updateProgress(value, maxValue = 100, animated = true) {{
                const percentage = Math.min(100, Math.max(0, (value / maxValue) * 100));
                
                if (animated) {{
                    progressFill.style.transition = 'width 0.5s ease-in-out';
                }} else {{
                    progressFill.style.transition = 'none';
                }}
                
                progressFill.style.width = percentage + '%';
                
                if (progressText) {{
                    progressText.textContent = `${{Math.round(percentage)}}%`;
                }}
            }}
            
            // Expose progress control
            if (window.overlay_{overlay.id.replace('-', '_')}) {{
                window.overlay_{overlay.id.replace('-', '_')}.updateProgress = updateProgress;
            }}
        }})();
        """
    
    def _render_error_overlay(self, error_message: str) -> Dict[str, str]:
        """Render error overlay when template rendering fails."""
        return {
            'html': f'''
            <div class="overlay-error">
                <h3>Overlay Render Error</h3>
                <p>{error_message}</p>
            </div>
            ''',
            'css': '''
            .overlay-error {
                background: rgba(255, 0, 0, 0.8);
                color: white;
                padding: 20px;
                border-radius: 5px;
                font-family: Arial, sans-serif;
                text-align: center;
            }
            ''',
            'js': '// Error overlay - no JavaScript needed'
        }
    
    def _render_error_page(self, error_message: str) -> str:
        """Render error page when page rendering fails."""
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>StreamOps Overlay Error</title>
            <style>
                body {{ 
                    margin: 0; 
                    padding: 50px; 
                    background: transparent; 
                    font-family: Arial, sans-serif;
                }}
                .error {{
                    background: rgba(255, 0, 0, 0.8);
                    color: white;
                    padding: 20px;
                    border-radius: 5px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Overlay Error</h2>
                <p>{error_message}</p>
            </div>
        </body>
        </html>
        '''


# Global renderer instance
overlay_renderer = OverlayRenderer()


# Utility functions for common rendering tasks
def render_sponsor_overlay(
    sponsor_name: str,
    sponsor_logo: Optional[str] = None,
    sponsor_message: Optional[str] = None,
    sponsor_url: Optional[str] = None,
    position: Optional[Dict[str, Any]] = None,
    style: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """Utility function to quickly render a sponsor overlay."""
    from app.api.schemas.overlays import OverlayResponse, OverlayType, OverlayPosition, OverlayStyle, OverlayContent, OverlayStatus
    from datetime import datetime
    
    overlay = OverlayResponse(
        id=str(uuid.uuid4()),
        name=f"Sponsor - {sponsor_name}",
        overlay_type=OverlayType.html,
        position=OverlayPosition(**(position or {"x": 50, "y": 50, "z_index": 10})),
        style=OverlayStyle(**(style or {})),
        content=OverlayContent(
            template_variables={
                "sponsor_name": sponsor_name,
                "sponsor_logo": sponsor_logo,
                "sponsor_message": sponsor_message,
                "sponsor_url": sponsor_url
            }
        ),
        enabled=True,
        status=OverlayStatus.active,
        tags=["sponsor"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return overlay_renderer.render_overlay(overlay)


def render_alert_overlay(
    alert_text: str,
    alert_type: str = "info",
    duration: Optional[int] = None,
    position: Optional[Dict[str, Any]] = None,
    style: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """Utility function to quickly render an alert overlay."""
    from app.api.schemas.overlays import OverlayResponse, OverlayType, OverlayPosition, OverlayStyle, OverlayContent, OverlayStatus
    from datetime import datetime
    
    overlay = OverlayResponse(
        id=str(uuid.uuid4()),
        name=f"Alert - {alert_type}",
        overlay_type=OverlayType.html,
        position=OverlayPosition(**(position or {"x": 100, "y": 100, "z_index": 20})),
        style=OverlayStyle(**(style or {})),
        content=OverlayContent(
            template_variables={
                "alert_text": alert_text,
                "alert_type": alert_type,
                "duration": duration
            }
        ),
        enabled=True,
        status=OverlayStatus.active,
        tags=["alert"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return overlay_renderer.render_overlay(overlay)


# Export main components
__all__ = [
    "OverlayRenderer",
    "overlay_renderer",
    "render_sponsor_overlay", 
    "render_alert_overlay"
]