#!/usr/bin/env python3
"""
Scan API functions to detect duplicates and create inventory.
Generates function_inventory.csv and duplicates.json
"""

import ast
import hashlib
import json
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from difflib import SequenceMatcher
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class FunctionScanner(ast.NodeVisitor):
    """AST visitor to extract function definitions"""
    
    def __init__(self, module_path: str):
        self.module_path = module_path
        self.functions = []
        self.current_class = None
        
    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        # Build qualified name
        qualname = node.name
        if self.current_class:
            qualname = f"{self.current_class}.{node.name}"
            
        # Get signature
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        signature = f"({', '.join(args)})"
        
        # Get docstring
        docstring = ast.get_docstring(node) or ""
        docstring_hash = hashlib.md5(docstring.encode()).hexdigest()[:8]
        
        # Normalize AST for comparison
        norm_ast = self.normalize_ast(node)
        norm_ast_hash = hashlib.md5(norm_ast.encode()).hexdigest()[:8]
        
        # Count lines of code
        loc = node.end_lineno - node.lineno + 1 if node.end_lineno else 1
        
        # Determine if public/private
        visibility = "private" if node.name.startswith("_") else "public"
        
        self.functions.append({
            "module_path": self.module_path,
            "qualname": qualname,
            "func_name": node.name,
            "signature": signature,
            "docstring_hash": docstring_hash,
            "norm_ast_hash": norm_ast_hash,
            "loc": loc,
            "visibility": visibility,
            "lineno": node.lineno,
            "docstring": docstring[:100]  # First 100 chars for reference
        })
        
        self.generic_visit(node)
        
    def normalize_ast(self, node) -> str:
        """Create normalized AST representation for comparison"""
        # Remove docstrings, comments, and normalize whitespace
        class Normalizer(ast.NodeTransformer):
            def visit_Expr(self, node):
                # Remove docstring expressions
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return None
                return node
                
            def visit_Name(self, node):
                # Normalize variable names (except function names)
                if not isinstance(node.ctx, ast.Store):
                    return node
                node.id = f"var_{hash(node.id) % 1000}"
                return node
                
        normalized = Normalizer().visit(ast.parse(ast.unparse(node)))
        return ast.unparse(normalized)

def scan_module(filepath: Path) -> List[Dict]:
    """Scan a Python module for function definitions"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
            
        module_path = str(filepath.relative_to(Path(__file__).parent.parent))
        scanner = FunctionScanner(module_path)
        scanner.visit(tree)
        return scanner.functions
    except Exception as e:
        print(f"Error scanning {filepath}: {e}")
        return []

def find_duplicates(functions: List[Dict]) -> Dict:
    """Find duplicate and near-duplicate functions"""
    duplicates = defaultdict(list)
    
    # Group by exact AST hash
    by_hash = defaultdict(list)
    for func in functions:
        by_hash[func['norm_ast_hash']].append(func)
    
    # Find exact duplicates
    group_id = 0
    for hash_val, group in by_hash.items():
        if len(group) > 1:
            group_id += 1
            duplicates[f"exact_{group_id}"] = {
                "type": "exact",
                "reason": "Identical normalized AST",
                "members": [{"module": f['module_path'], "qualname": f['qualname']} for f in group],
                "ast_hash": hash_val,
                "canonical_suggestion": group[0]['module_path']  # Prefer first found
            }
    
    # Find near-duplicates by name
    by_name = defaultdict(list)
    for func in functions:
        by_name[func['func_name']].append(func)
    
    for name, group in by_name.items():
        if len(group) > 1:
            # Compare each pair
            for i, func1 in enumerate(group):
                for func2 in group[i+1:]:
                    # Skip if already in exact duplicates
                    if func1['norm_ast_hash'] == func2['norm_ast_hash']:
                        continue
                        
                    # Compare normalized AST as strings
                    similarity = SequenceMatcher(None, 
                                                func1.get('norm_ast', ''), 
                                                func2.get('norm_ast', '')).ratio()
                    
                    if similarity >= 0.85:  # Near-duplicate threshold
                        group_id += 1
                        duplicates[f"near_{group_id}"] = {
                            "type": "near",
                            "reason": f"Similar implementation (similarity: {similarity:.2f})",
                            "members": [
                                {"module": func1['module_path'], "qualname": func1['qualname']},
                                {"module": func2['module_path'], "qualname": func2['qualname']}
                            ],
                            "similarity_score": similarity,
                            "canonical_suggestion": suggest_canonical(func1, func2)
                        }
    
    return dict(duplicates)

def suggest_canonical(func1: Dict, func2: Dict) -> str:
    """Suggest which implementation should be canonical"""
    # Prefer services over routers
    if 'services' in func1['module_path'] and 'routers' in func2['module_path']:
        return func1['module_path']
    elif 'services' in func2['module_path'] and 'routers' in func1['module_path']:
        return func2['module_path']
    
    # Prefer non-manager modules
    if '_manager' not in func1['module_path'] and '_manager' in func2['module_path']:
        return func1['module_path']
    elif '_manager' not in func2['module_path'] and '_manager' in func1['module_path']:
        return func2['module_path']
    
    # Default to first
    return func1['module_path']

def trace_usage(func_name: str, search_dirs: List[Path]) -> List[str]:
    """Find all usages of a function"""
    usages = []
    for dir_path in search_dirs:
        for py_file in dir_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        if f"{func_name}(" in line and "def " not in line:
                            usages.append(f"{py_file}:{i}")
            except:
                pass
    return usages

def main():
    """Main entry point"""
    project_root = Path(__file__).parent.parent
    api_dir = project_root / "app" / "api"
    
    # Modules to scan
    scan_paths = [
        api_dir / "db" / "database.py",
        *(api_dir / "routers").glob("*.py"),
        *(api_dir / "schemas").glob("*.py"),
        *(api_dir / "services").glob("*.py"),
    ]
    
    print("Scanning API functions...")
    all_functions = []
    for filepath in scan_paths:
        if filepath.exists() and filepath.suffix == '.py':
            functions = scan_module(filepath)
            all_functions.extend(functions)
            print(f"  Found {len(functions)} functions in {filepath.name}")
    
    print(f"\nTotal functions found: {len(all_functions)}")
    
    # Write inventory
    inventory_file = project_root / "function_inventory.csv"
    with open(inventory_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "module_path", "qualname", "func_name", "signature", 
            "docstring_hash", "norm_ast_hash", "loc", "visibility", "lineno"
        ])
        writer.writeheader()
        for func in all_functions:
            writer.writerow({k: v for k, v in func.items() 
                           if k not in ['docstring', 'norm_ast']})
    print(f"Wrote inventory to {inventory_file}")
    
    # Find duplicates
    print("\nSearching for duplicates...")
    duplicates = find_duplicates(all_functions)
    
    # Add usage information for duplicates
    print("Tracing usage patterns...")
    for group_id, group_data in duplicates.items():
        for member in group_data['members']:
            # Extract function name from qualname
            func_name = member['qualname'].split('.')[-1]
            usages = trace_usage(func_name, [api_dir])
            member['usage_count'] = len(usages)
            member['usage_samples'] = usages[:3]  # First 3 usages
    
    # Write duplicates report
    duplicates_file = project_root / "duplicates.json"
    with open(duplicates_file, 'w', encoding='utf-8') as f:
        json.dump(duplicates, f, indent=2)
    print(f"Found {len(duplicates)} duplicate groups")
    print(f"Wrote duplicates report to {duplicates_file}")
    
    # Print summary
    print("\n=== DUPLICATE SUMMARY ===")
    for group_id, group_data in duplicates.items():
        print(f"\n{group_id} ({group_data['type']}): {group_data['reason']}")
        for member in group_data['members']:
            usage_info = f"({member.get('usage_count', 0)} usages)"
            print(f"  - {member['module']}: {member['qualname']} {usage_info}")
        print(f"  Suggested canonical: {group_data.get('canonical_suggestion', 'N/A')}")

if __name__ == "__main__":
    main()