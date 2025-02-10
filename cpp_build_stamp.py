#!/usr/bin/env python3
"""
A tool to modify constant values in C++ header files while preserving the structure.
Uses libclang to parse and modify C++ code safely. Supports placeholder expansion
for dynamic values like dates and times.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Callable, Any
import argparse
import logging
import re
import sys

import clang.cindex
from tzlocal import get_localzone
import pytz

@dataclass
class PlaceholderContext:
    """Context for placeholder expansion containing current state and settings."""
    now: datetime
    date_format: str
    time_format: str
    timezone: str
    current_value: Optional[str] = None  # Added to store current value    

# Define placeholder expansions with extra help text
PLACEHOLDERS = {
    'date': {
        'func': lambda ctx: ctx.now.strftime(ctx.date_format),
        'args': ['--date_format'],
        'default_args': {'date_format': '%d %b %Y'},
        'help': 'Format string for date placeholders.',
        'p_help': 'current date'
    },
    'time': {
        'func': lambda ctx: ctx.now.strftime(ctx.time_format),
        'args': ['--time_format'],
        'default_args': {'time_format': '%I:%M:%S %p %Z'},
        'help': 'Format string for time placeholders.',
        'p_help': 'current time'
    },
    '++': {
        'func': lambda ctx: str(int(ctx.current_value) + 1) if ctx.current_value else '1',
        'args': [],
        'default_args': {},
        'help': 'Increment the current value by 1.',
        'p_help': 'increment current value'
    }
}

class LiteralKind(Enum):
    """Supported literal types for modification."""
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()

    @classmethod
    def from_cursor_kind(cls, cursor_kind: clang.cindex.CursorKind) -> Optional['LiteralKind']:
        """Convert a clang cursor kind to our literal kind."""
        kind_map = {
            clang.cindex.CursorKind.INTEGER_LITERAL: cls.INTEGER,
            clang.cindex.CursorKind.FLOATING_LITERAL: cls.FLOAT,
            clang.cindex.CursorKind.STRING_LITERAL: cls.STRING
        }
        return kind_map.get(cursor_kind)

@dataclass
class SourceRange:
    """Represents a range in source code."""
    start_offset: int
    end_offset: int

    def __post_init__(self):
        if self.start_offset > self.end_offset:
            raise ValueError("Start offset cannot be greater than end offset")

@dataclass
class Variable:
    """Represents a variable declaration and its initializer."""
    name: str
    declaration_range: SourceRange
    initializer_range: SourceRange
    literal_kind: LiteralKind

@dataclass
class Modification:
    """Represents a requested modification to a variable."""
    namespace: str
    variable_name: str
    new_value: str

class PlaceholderExpander:
    """Handles expansion of placeholders in values."""
    
    def __init__(self, ctx: PlaceholderContext):
        self.ctx = ctx
        self._placeholder_pattern = re.compile(r'\{([^}]+)\}')
    
    def expand(self, value: str) -> str:
        """Expand all placeholders in a value."""
        def replace(match):
            placeholder = match.group(1)
            if placeholder not in PLACEHOLDERS:
                raise ValueError(f"Unknown placeholder: {placeholder}")
            return PLACEHOLDERS[placeholder]['func'](self.ctx)
            
        return self._placeholder_pattern.sub(replace, value)

class ConstantModifier:
    """Handles finding and modifying constants in C++ code."""

    DEFAULT_CLANG_ARGS = ["-std=c++26"]

    def __init__(self, file_path: Union[str, Path], clang_args: Optional[List[str]] = None, 
                 expander: Optional[PlaceholderExpander] = None, verbose: bool = False):
        """Initialize the modifier with a file path and optional clang arguments."""
        self.file_path = Path(file_path)
        self.clang_args = clang_args or self.DEFAULT_CLANG_ARGS
        self.expander = expander
        
        # Append "-x c++" to clang args if not already present
        if not any(arg.startswith("-x") for arg in self.clang_args):
            self.clang_args = self.clang_args + ["-x", "c++"]
            
        self._setup_logging(verbose)
        self._setup_clang()
        
    def _setup_logging(self, verbose: bool) -> None:
        """Configure logging based on verbosity."""
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            format='[%(levelname)s] %(message)s',
            level=level
        )

    def _setup_clang(self) -> None:
        """Initialize clang parser."""
        self.index = clang.cindex.Index.create()
        self.translation_unit = self.index.parse(
            str(self.file_path),
            args=self.clang_args
        )

    def _extract_literal(self, expr_cursor) -> Tuple[Optional[SourceRange], Optional[LiteralKind]]:
        """Extract literal information from an expression cursor."""
        for child in expr_cursor.get_children():
            kind = LiteralKind.from_cursor_kind(child.kind)
            if kind:
                return SourceRange(
                    child.extent.start.offset,
                    child.extent.end.offset
                ), kind
            
            if child.kind == clang.cindex.CursorKind.UNEXPOSED_EXPR:
                result = self._extract_literal(child)
                if result[0]:
                    return result
                    
        return None, None

    def _find_variables(self, cursor, namespace: str, variables: List[str]) -> Dict[str, Variable]:
        """Recursively find multiple variables in the specified namespace or global scope."""
        found_vars: Dict[str, Variable] = {}
        remaining_vars = set(variables)

        def process_scope(cursor, in_target_namespace: bool):
            for child in cursor.get_children():
                if (child.kind == clang.cindex.CursorKind.VAR_DECL and 
                    child.spelling in remaining_vars and
                    in_target_namespace):
                    var = self._process_variable_declaration(child)
                    if var:
                        found_vars[child.spelling] = var
                        remaining_vars.remove(child.spelling)
                        if not remaining_vars:  # Early exit if all variables found
                            return True
                            
                # For global namespace, process all scopes
                if namespace == "":
                    process_scope(child, True)
                # For specific namespace, only process matching namespace
                elif (child.kind == clang.cindex.CursorKind.NAMESPACE and 
                      child.spelling == namespace):
                    process_scope(child, True)
                else:
                    process_scope(child, in_target_namespace)

        # Start processing from root with appropriate namespace flag
        process_scope(cursor, namespace == "")
        return found_vars

    def _process_variable_declaration(self, cursor) -> Optional[Variable]:
        """Process a variable declaration cursor to extract relevant information."""
        logging.debug(f"Processing variable: {cursor.spelling}")
        
        for child in cursor.get_children():
            # Check for direct literals first
            kind = LiteralKind.from_cursor_kind(child.kind)
            if kind:
                return Variable(
                    name=cursor.spelling,
                    declaration_range=SourceRange(
                        cursor.extent.start.offset,
                        cursor.extent.end.offset
                    ),
                    initializer_range=SourceRange(
                        child.extent.start.offset,
                        child.extent.end.offset
                    ),
                    literal_kind=kind
                )
            # Then check for unexposed expressions that might contain literals
            elif child.kind == clang.cindex.CursorKind.UNEXPOSED_EXPR:
                init_range, kind = self._extract_literal(child)
                if init_range and kind:
                    return Variable(
                        name=cursor.spelling,
                        declaration_range=SourceRange(
                            cursor.extent.start.offset,
                            cursor.extent.end.offset
                        ),
                        initializer_range=init_range,
                        literal_kind=kind
                    )
        return None

    def _get_current_value(self, range_: SourceRange) -> str:
        """Read the current value from the file at the given range."""
        with open(self.file_path, "rb") as f:
            content = f.read().decode("utf-8")
            current_value = content[range_.start_offset:range_.end_offset]
            
            # Strip quotes for string literals
            if current_value.startswith('"') and current_value.endswith('"'):
                current_value = current_value[1:-1]
                
            return current_value

    def _format_new_value(self, value: str, kind: LiteralKind, current_range: Optional[SourceRange] = None) -> str:
        """Format a new value according to its literal kind."""
        # Get current value if range is provided
        current_value = None
        if current_range:
            current_value = self._get_current_value(current_range)
        
        # Set current value in context if expander exists
        if self.expander:
            self.expander.ctx.current_value = current_value
            value = self.expander.expand(value)
            
        if kind == LiteralKind.INTEGER:
            return str(int(value))
        elif kind == LiteralKind.FLOAT:
            return str(float(value))
        elif kind == LiteralKind.STRING:
            return f'"{value}"'
        raise ValueError(f"Unsupported literal kind: {kind}")

    def modify_constants(self, modifications: List[Modification]) -> bool:
        """Find and modify multiple constants in the specified namespace."""
        # Group modifications by namespace for efficient processing
        by_namespace: Dict[str, List[Tuple[str, str]]] = {}
        for mod in modifications:
            by_namespace.setdefault(mod.namespace, []).append(
                (mod.variable_name, mod.new_value)
            )

        # Process each namespace
        all_changes: List[Tuple[SourceRange, str]] = []
        
        for namespace, var_updates in by_namespace.items():
            var_names = [name for name, _ in var_updates]
            found_vars = self._find_variables(
                self.translation_unit.cursor,
                namespace,
                var_names
            )

            # Prepare all modifications
            for var_name, new_value in var_updates:
                variable = found_vars.get(var_name)
                if not variable:
                    if namespace:
                        logging.error(
                            f"Variable '{var_name}' not found in namespace '{namespace}'"
                        )
                    else:
                        logging.error(f"Variable '{var_name}' not found in global scope")

                    return False

                try:
                    new_initializer = self._format_new_value(
                        new_value, 
                        variable.literal_kind,
                        variable.initializer_range  # Pass the range to get current value
                    )
                    all_changes.append(
                        (variable.initializer_range, new_initializer)
                    )
                except ValueError as e:
                    logging.error(f"Error formatting new value: {e}")
                    return False

        # Sort changes by offset in descending order to preserve offsets
        all_changes.sort(key=lambda x: x[0].start_offset, reverse=True)

        # Apply all changes
        for range_, new_text in all_changes:
            self._modify_file(range_, new_text)

        logging.info(f"Successfully applied {len(all_changes)} modifications")
        return True

    def _modify_file(self, range_: SourceRange, new_text: str) -> None:
        """Modify the file content at the given byte range."""
        with open(self.file_path, "rb") as f:
            content = f.read().decode("utf-8")
            
        modified_content = (
            content[:range_.start_offset] +
            new_text +
            content[range_.end_offset:]
        )
        
        with open(self.file_path, "wb") as f:
            f.write(modified_content.encode("utf-8"))

def parse_var_value(s: str) -> Tuple[str, str]:
    """Parse a variable=value string into its components."""
    try:
        var, value = s.split('=', 1)
        return var.strip(), value.strip()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid format: {s}. Use 'variable=value'"
        )

def parse_args():
    """Parse command line arguments with optional namespace."""
    parent_parser = argparse.ArgumentParser(add_help=False)
    
    # Add basic options
    parent_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parent_parser.add_argument(
        "--timezone",
        default=str(get_localzone()),
        help="Timezone for date/time expansion (default: system timezone)"
    )
    
    # Add placeholder-specific arguments from PLACEHOLDERS
    for name, config in PLACEHOLDERS.items():
        for arg in config['args']:
            parent_parser.add_argument(
                arg,
                default=config['default_args'][arg.lstrip('-').replace('-', '_')],
                help=config['help']
            )
    
    # Create the main parser 
    parser = argparse.ArgumentParser(
        description="Modify constant values in a C++ file.",
        parents=[parent_parser]
    )

    # Add file argument
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the C++ header file"
    )
    
    parser.add_argument(
        "namespace",
        nargs="?",
        help="Optional namespace containing the variables"
    )
    
    parser.add_argument(
        "modifications",
        nargs="+",
        metavar="VAR=VALUE",
        type=parse_var_value,
        help=f"Variable modifications. Values may include: " + 
             ", ".join([f"{{{name}}}: {config['p_help']}" for name, config in PLACEHOLDERS.items()])
    )

    # Add clang-args as a separate argument that must come last
    parser.add_argument(
        "--clang-args",
        nargs=argparse.REMAINDER,
        help=f"Additional arguments to pass to clang (default: {' '.join(ConstantModifier.DEFAULT_CLANG_ARGS)}). "
             "Must be specified last."
    )

    args = parser.parse_args()
    
    # Validate no '=' in namespace if provided
    if args.namespace and '=' in args.namespace:
        # This namespace is actually a variable=value pair. Move it.
        args.modifications.append(parse_var_value(args.namespace))
        args.namespace = None
    
    return args, args.namespace, args.modifications

def main() -> int:
    """Entry point for the script."""
    args, namespace, modifications = parse_args()
    
    # Use clang args as provided
    clang_args = args.clang_args if args.clang_args else None
    
    # Set up timezone and context for placeholder expansion
    try:
        tz = pytz.timezone(args.timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        logging.error(f"Unknown timezone: {args.timezone}")
        return 1
        
    ctx = PlaceholderContext(
        now=datetime.now(tz),
        date_format=args.date_format,
        time_format=args.time_format,
        timezone=args.timezone
    )
    
    expander = PlaceholderExpander(ctx)

    modifier = ConstantModifier(
        args.file,
        clang_args,
        expander,
        args.verbose
    )

    # Create modifications list with optional namespace
    modifications = [
        Modification(namespace or "", var, value)
        for var, value in modifications
    ]
    
    success = modifier.modify_constants(modifications)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())