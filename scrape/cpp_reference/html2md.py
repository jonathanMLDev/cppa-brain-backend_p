import re
import sys
from pathlib import Path
from html import unescape
from bs4 import BeautifulSoup

# import html5lib
# from html5lib import serializer

from lxml import html

import pypandoc


def preprocess_html_content(html_content):
    """
    Preprocess HTML content using lxml to fix malformed HTML (close tags, etc.).

    Args:
        html_content: The HTML content as a string

    Returns:
        str: Preprocessed HTML with fixed structure
    """
    # Remove encoding declarations that cause issues with lxml
    # lxml doesn't support Unicode strings with encoding declarations
    html_content_clean = re.sub(
        r"<\?xml[^>]*\?>", "", html_content, flags=re.IGNORECASE
    )
    html_content_clean = re.sub(
        r"<!DOCTYPE[^>]*>", "", html_content_clean, flags=re.IGNORECASE
    )

    # Use HTMLParser which is more lenient with malformed HTML
    parser = html.HTMLParser(encoding="utf-8", recover=True)

    try:
        # Convert to bytes for lxml
        if isinstance(html_content_clean, str):
            html_bytes = html_content_clean.encode("utf-8")
        else:
            html_bytes = html_content_clean

        tree = html.fromstring(html_bytes, parser=parser)
        result = html.tostring(tree, pretty_print=True, encoding="utf-8")
        return result.decode("utf-8")
    except Exception as e:
        # If lxml fails, return original content
        print(f"Warning: lxml preprocessing failed: {e}")
        return html_content


def preprocess_html_for_metadata(html_content):
    """
    Preprocess HTML to move body content that's outside <main> into <main> tag.

    Args:
        html_content: The HTML content as a string

    Returns:
        str: HTML with body content moved into main tag
    """
    # 1. Find body tag

    # html_content = preprocess_tables_in_blockquotes(html_content)

    body_start_match = re.search(r"<body\b[^>]*>", html_content, re.IGNORECASE)
    if not body_start_match:
        # No body tag found, return as-is
        return preprocess_html_content(html_content)

    body_open = body_start_match.group(0)
    body_start_pos = body_start_match.end()

    # Find closing </body> tag
    body_close_match = re.search(
        r"</body>", html_content[body_start_pos:], re.IGNORECASE
    )
    if body_close_match:
        body_end_pos = body_start_pos + body_close_match.start()
        body_content = html_content[body_start_pos:body_end_pos]
        body_close = "</body>"
        remaining_after_body = html_content[body_start_pos + body_close_match.end() :]
    else:
        # No closing tag, use end of file as closing point
        body_content = html_content[body_start_pos:]
        body_close = "</body>"
        remaining_after_body = ""

    # 2. Find main tag within body content
    main_start_match = re.search(r"<main\b[^>]*>", body_content, re.IGNORECASE)
    if not main_start_match:
        # No main tag found, return as-is
        return preprocess_html_content(html_content)

    main_open = main_start_match.group(0)
    main_start_pos = main_start_match.end()

    # Find closing </main> tag
    main_close_match = re.search(
        r"</main>", body_content[main_start_pos:], re.IGNORECASE
    )
    if main_close_match:
        main_end_pos = main_start_pos + main_close_match.start()
        main_content = body_content[main_start_pos:main_end_pos]
        main_close = "</main>"
    else:
        # No closing tag, use end of body content as closing point
        main_content = body_content[main_start_pos:]
        main_close = "</main>"

    # 3. If both exist, move the content of body which is not contained in main into main tag

    # Get the position of main tag in body content
    main_start = main_start_match.start()
    if main_close_match:
        main_end = main_start_pos + main_close_match.end()
    else:
        main_end = len(body_content)

    # Extract content before main tag
    before_main = body_content[:main_start].strip()

    # Extract content after main tag
    after_main = body_content[main_end:].strip()

    # If no content to move, return as-is
    if not before_main and not after_main:
        return preprocess_html_content(html_content)

    # Build new main content:
    # - Content before main goes at the front
    # - Original main content in the middle
    # - Content after main goes at the end
    new_main_content_parts = []

    if before_main:
        new_main_content_parts.append(before_main)

    new_main_content_parts.append(main_content)

    if after_main:
        new_main_content_parts.append(after_main)

    new_main_content = "\n".join(new_main_content_parts)
    new_main_tag = main_open + "\n" + new_main_content + "\n" + main_close

    # Reconstruct body content: remove content before/after main, keep only main tag
    new_body_content = new_main_tag

    new_body_content = (
        html_content[: body_start_match.start()]
        + body_open
        + "\n"
        + new_body_content
        + "\n"
        + body_close
        + remaining_after_body
    )

    # Reconstruct HTML
    return preprocess_html_content(new_body_content)


def convert_html_tables_to_markdown(text):
    """
    Convert HTML table tags to markdown table format.

    Args:
        text: The markdown text that may contain HTML table tags

    Returns:
        str: Text with HTML tables converted to markdown tables
    """
    # Pattern to match HTML table blocks
    # Also capture content before <table> tag on the same line (to detect blockquote context)
    table_pattern = r"([^\n]*?)<table[^>]*>(.*?)</table>"

    def convert_table(match):
        prefix_table_content = match.group(1)  # Content before <table> on same line
        table_html = match.group(2)  # Table content

        # Remove colgroup tags
        table_html = re.sub(
            r"<colgroup>.*?</colgroup>", "", table_html, flags=re.DOTALL
        )
        table_html = re.sub(r"<col[^>]*/?>", "", table_html)

        # Extract rows from thead and tbody
        rows = []

        # Get header row from thead
        thead_match = re.search(r"<thead>(.*?)</thead>", table_html, re.DOTALL)
        if thead_match:
            thead_content = thead_match.group(1)
            header_row_match = re.search(
                r"<tr[^>]*/?>(.*?)</tr>", thead_content, re.DOTALL
            )
            if header_row_match:
                header_cells = re.findall(
                    r"<t[hd][^>]*/?>(.*?)</t[hd]>",
                    header_row_match.group(1),
                    re.DOTALL,
                )
                # Clean up cell content - handle code tags and other HTML
                cleaned_header = []
                for cell in header_cells:
                    # Convert code tags to backticks
                    cell = re.sub(r"<code[^>]*/?>", "`", cell)
                    cell = re.sub(r"</code>", "` ", cell)
                    # Remove other HTML tags (both opening and closing)
                    cell = re.sub(
                        r"<[^/>]+>", "", cell
                    )  # Opening tags: <tag>, <tag attr="value">
                    cell = re.sub(r"</[^>]+>", "", cell)  # Closing tags: </tag>
                    # Clean up whitespace
                    cell = " ".join(cell.split()).strip()
                    cleaned_header.append(cell)
                rows.append(cleaned_header)

        # Get data rows from tbody
        tbody_match = re.search(r"<tbody[^>]*/?>(.*?)</tbody>", table_html, re.DOTALL)
        if tbody_match:
            tbody_content = tbody_match.group(1)
            data_rows = re.findall(r"<tr[^>]*/?>(.*?)</tr>", tbody_content, re.DOTALL)
            for row_html in data_rows:
                cells = re.findall(r"<t[hd][^>]*/?>(.*?)</t[hd]>", row_html, re.DOTALL)
                # Clean up cell content - convert <br> to space, handle code tags
                cleaned_cells = []
                for cell in cells:
                    # Convert <br> tags to space
                    # cell = re.sub(r"<br[^>]*/?>", "\n\n", cell)
                    # Convert code tags to backticks
                    cell = re.sub(r"<code[^>]*/?>", "`", cell)
                    cell = re.sub(r"</code>", "` ", cell)
                    # Remove other HTML tags (both opening and closing)
                    cell = re.sub(
                        r"<[^/>]+>", "", cell
                    )  # Opening tags: <tag>, <tag attr="value">
                    cell = re.sub(r"</[^>]+>", "", cell)  # Closing tags: </tag>
                    # Clean up whitespace
                    cell = " ".join(cell.split()).strip()
                    cleaned_cells.append(cell)
                if cleaned_cells:
                    rows.append(cleaned_cells)

        # If no thead/tbody, try to get all rows directly
        if not rows:
            all_rows = re.findall(r"<tr[^>]*/?>(.*?)</tr>", table_html, re.DOTALL)
            for row_html in all_rows:
                cells = re.findall(r"<t[hd][^>]*/?>(.*?)</t[hd]>", row_html, re.DOTALL)
                cleaned_cells = []
                for cell in cells:
                    # Convert <br> tags to space
                    # cell = re.sub(r"<br\s*/?>", "\n\n", cell)
                    # Convert code tags to backticks
                    cell = re.sub(r"<code[^>]*/?>", "`", cell)
                    cell = re.sub(r"</code>", "` ", cell)
                    # Remove other HTML tags (both opening and closing)
                    cell = re.sub(
                        r"<[^/>]+>", "", cell
                    )  # Opening tags: <tag>, <tag attr="value">
                    cell = re.sub(r"</[^>]+>", "", cell)  # Closing tags: </tag>

                    # Clean up whitespace
                    cell = " ".join(cell.split()).strip()
                    cleaned_cells.append(cell)
                if cleaned_cells:
                    rows.append(cleaned_cells)

        if not rows:
            return match.group(0)  # Return original if we can't parse

        # Determine number of columns from first row
        num_cols = len(rows[0]) if rows else 0
        if num_cols == 0:
            return match.group(0)

        # Build markdown table
        markdown_lines = []

        # Add header row
        if rows:
            header = rows[0]
            markdown_lines.append("| " + " | ".join(header) + " |")
            # Add separator
            markdown_lines.append("| " + " | ".join(["---"] * num_cols) + " |")
            # Add data rows
            for row in rows[1:]:
                # Pad row if needed
                while len(row) < num_cols:
                    row.append(" ")
                markdown_lines.append("| " + " | ".join(row[:num_cols]) + " |")

        # Add prefix to each line of the table if prefix exists
        if prefix_table_content:
            # Prepend prefix to each line of the markdown table
            prefixed_lines = [prefix_table_content + line for line in markdown_lines]
            markdown_table = "\n".join(prefixed_lines)
        else:
            markdown_table = "\n".join(markdown_lines)

        return markdown_table

    # Convert all HTML tables
    text = re.sub(table_pattern, convert_table, text, flags=re.DOTALL | re.IGNORECASE)

    return text


def post_process_markdown(text):
    """
    Post-process markdown output to fix common conversion issues.

    Args:
        text: The markdown text to process

    Returns:
        str: Processed markdown text
    """
    # Remove excessive blank lines (more than 2 consecutive blank lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Fix broken table at the beginning - remove malformed table header
    lines = text.split("\n")
    if len(lines) > 2:
        # Check for broken table pattern: | ... | followed by blank line and |---|
        # This happens when pandoc doesn't properly convert HTML tables
        if (
            lines[0].strip().startswith("|")
            and "---" not in lines[0]
            and lines[1].strip() == ""
            and len(lines) > 2
            and "---" in lines[2]
        ):
            # This looks like a broken table, try to fix it
            # Check if we can reconstruct the table properly
            if len(lines) > 3 and lines[3].strip().startswith("|"):
                # Remove the broken first line (it's usually a duplicate header)
                lines = lines[1:]
            else:
                # Remove the broken table entirely (can't be fixed)
                lines = lines[3:]

    # Fix tables that have proper structure but need header reconstruction
    # Look for patterns like: | col1 | col2 | -> blank -> |---|---| -> | val1 | val2 |
    fixed_lines = []
    i = 0
    while i < len(lines):
        # Check if current line looks like a table row
        if (
            i < len(lines) - 2
            and lines[i].strip().startswith("|")
            and "---" in lines[i + 1]
        ):
            # This is a valid table, keep it
            fixed_lines.append(lines[i])
            fixed_lines.append(lines[i + 1])
            i += 2
            # Add table rows until we hit a non-table line
            while i < len(lines) and lines[i].strip().startswith("|"):
                fixed_lines.append(lines[i])
                i += 1
            continue
        fixed_lines.append(lines[i])
        i += 1

    text = "\n".join(fixed_lines)

    # Remove list numbers from table of contents links (but keep section numbers in link text)
    # Pattern: "1.  [1 Brief History](#History)" -> "- [1 Brief History](#History)"
    # Pattern: "    1.  [4.1 Text](#link)" -> "    - [4.1 Text](#link)"
    # This replaces markdown list numbering with dash but preserves section numbers inside brackets
    # Match: optional whitespace + number + period + spaces + opening bracket
    text = re.sub(r"^(\s*)\d+\.\s+(\[)", r"\1- \2", text, flags=re.MULTILINE)

    # Remove anchor tags from headings (GitHub-style anchors)
    # Pattern: ## <a href="#..." id="user-content-..." class="anchor" ...></a>Heading Text
    # This handles GitHub-style anchor links that appear in headings
    # Handle anchors with class="anchor" (most common case)
    text = re.sub(
        r'(#{1,6})\s*<a[^>]*class="anchor"[^>]*>(?:<[^>]+>)*</a>\s*',
        r"\1 ",
        text,
    )
    # Handle anchors with id="user-content-" (GitHub pattern)
    text = re.sub(
        r'(#{1,6})\s*<a[^>]*id="user-content-[^"]*"[^>]*>(?:<[^>]+>)*</a>\s*',
        r"\1 ",
        text,
    )
    # Remove any remaining anchor tags in headings (more general pattern)
    # This catches anchor tags with href="#..." that might be in headings
    text = re.sub(
        r'(#{1,6})\s*<a[^>]*href="#[^"]*"[^>]*>(?:<[^>]+>)*</a>\s*',
        r"\1 ",
        text,
    )
    # Final catch-all for any anchor tags in headings (handles nested tags like <span>)
    text = re.sub(
        r"(#{1,6})\s*<a[^>]*>.*?</a>\s*",
        r"\1 ",
        text,
        flags=re.DOTALL,
    )

    # Convert HTML tables to markdown tables

    # Remove standalone HTML tags that weren't converted (div, span, etc.)
    # But preserve content inside them
    text = re.sub(r"<div[^>]*>\s*", "", text)
    text = re.sub(r"\s*</div>", "", text)
    text = re.sub(r"<span[^>]*>\s*", "", text)
    text = re.sub(r"\s*</span>", "", text)

    # Convert remaining HTML formatting tags to markdown
    text = re.sub(r"<ins[^>]*>", "", text)
    text = re.sub(r"</ins>", "", text)
    text = re.sub(r"<del[^>]*>", "~~", text)
    text = re.sub(r"</del>", "~~ ", text)
    text = re.sub(r"<u[^>]*>", "", text)
    text = re.sub(r"</u>", "", text)
    text = re.sub(r"<tt[^>]*>", "`", text)
    text = re.sub(r"</tt>", "` ", text)
    # Handle code tags that might be outside code blocks
    # First, fix malformed code tags (missing closing tag)
    text = re.sub(r"<code[^>]*>([^<`]+)(?![^<]*</code>)", r"`\1` ", text)
    # Then handle properly formed code tags
    text = re.sub(r"<code[^>]*>", "`", text)
    text = re.sub(r"</code>", "` ", text)
    # Fix double backticks that might have been created
    text = re.sub(r"``([^`]+)``", r"`\1`", text)
    text = re.sub(r"<strong[^>]*>", "**", text)
    text = re.sub(r"</strong>", "** ", text)
    text = re.sub(r"<b\b[^>]*>", "**", text)
    text = re.sub(r"</b>", "** ", text)
    text = re.sub(r"<em[^>]*>", "*", text)
    text = re.sub(r"</em>", "* ", text)
    text = re.sub(r"<i[^>]*>", "*", text)
    text = re.sub(r"</i>", "* ", text)

    # Fix nested code formatting (double backticks)
    text = re.sub(r"``([^`]+)``", r"`\1`", text)

    # Fix code blocks that have extra blank lines
    # Remove blank lines immediately after opening ```
    text = re.sub(r"```\n\n+", "```\n", text)
    # Remove blank lines immediately before closing ```
    text = re.sub(r"\n\n+```", "\n```", text)

    # Fix code blocks that should be fenced but aren't
    # Detect C++ function declarations and code that should be in code blocks
    # This handles cases where GitHub-style highlight divs weren't converted properly
    lines = text.split("\n")
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this looks like the start of a code block that's missing fences
        # Look for C++ function declarations or templates after a blank line
        # Pattern: blank line, then "path " or "template" or function-like declarations
        if (
            i > 0
            and lines[i - 1].strip() == ""
            and not line.strip().startswith(("#", ">", "-", "*", "|", "```"))
            and (
                line.strip().startswith("path ")
                or line.strip().startswith("template")
                or (re.search(r"^\s*path\s+\w+\s*\(", line) and ";" in line)
            )
        ):

            # Collect consecutive code-like lines
            code_lines = []
            j = i
            blank_count = 0

            while j < len(lines):
                current_line = lines[j]
                stripped = current_line.strip()

                # Stop if we hit markdown syntax (headings, lists, etc.)
                if stripped.startswith(("#", ">", "-", "*", "|", "```")):
                    break

                # Handle blank lines - allow one, but stop if we get two consecutive
                if stripped == "":
                    blank_count += 1
                    if blank_count > 1:
                        break
                    code_lines.append(current_line)
                    j += 1
                    continue

                blank_count = 0

                # Check if line looks like C++ code (function declarations, templates, etc.)
                is_code = (
                    stripped.startswith("path ")
                    or stripped.startswith("template")
                    or re.match(
                        r"^\s*(path|template|class|struct|namespace)\s+", stripped
                    )
                    or (
                        re.search(r"\([^)]*\)\s*;", stripped)
                        and ("path" in stripped.lower() or "const" in stripped.lower())
                    )
                    or (
                        stripped.startswith("    ")
                        and re.search(r"\([^)]*\)", stripped)
                    )
                )

                if is_code:
                    code_lines.append(current_line)
                    j += 1
                else:
                    # If we have enough code lines, this is probably a code block
                    # Otherwise, it's probably not
                    break

            # If we collected multiple code lines (at least 2 non-blank), wrap them
            non_blank_lines = [l for l in code_lines if l.strip()]
            if len(non_blank_lines) >= 2:
                # Remove trailing blank lines from code block
                while code_lines and code_lines[-1].strip() == "":
                    code_lines.pop()

                fixed_lines.append("```cpp")
                fixed_lines.extend(code_lines)
                fixed_lines.append("```")
                i = j
                continue

        fixed_lines.append(line)
        i += 1

    text = "\n".join(fixed_lines)

    # Fix blockquotes that have excessive spacing
    text = re.sub(r"\n\n+> ", "\n\n> ", text)

    # Remove empty headings (headings with only # characters and no text)
    # Pattern: lines that start with 1-6 # characters followed only by whitespace
    # This fixes cases where Pandoc converts empty HTML headings to empty markdown headings
    # Process line by line to handle edge cases properly
    lines = text.split("\n")
    filtered_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this is an empty heading (1-6 # characters followed only by whitespace)
        if re.match(r"^#{1,6}\s*$", line):
            # Skip this empty heading line
            # Don't skip the next blank line - preserve spacing between content
            i += 1  # Skip the empty heading itself
            continue
        filtered_lines.append(line)
        i += 1

    text = "\n".join(filtered_lines)

    # Clean up any triple+ newlines that might have been created
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Clean up excessive spacing around headings (after removing empty ones)
    text = re.sub(r"\n{2,}(#{1,6}\s)", r"\n\n\1", text)

    # Remove trailing whitespace from lines
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Remove blank lines at the start of the file
    text = text.lstrip("\n")

    text = convert_html_tables_to_markdown(text)

    # Convert HTML anchor tags in markdown link brackets to proper markdown links
    # Pattern: \[<a href="..." ...>...</a>\] (with escaped brackets and optional attributes)
    # Convert to: [...](...)
    # Example: \[<a href="#ref-P1120R0" role="doc-biblioref">P1120R0</a>\] -> [P1120R0](#ref-P1120R0)
    # Example: \[<a href="#3.9/2">3.9 2-3, basic.types</a>\] -> [3.9 2-3, basic.types](#3.9/2)
    text = re.sub(r'\\\[<a href="([^"]+)"[^>]*>([^<]+)</a>\\\]', r"[[\2](\1)]", text)

    # Ensure file ends with a single newline
    text = text.rstrip() + "\n"

    return text


def convert_html_to_md(
    html_path, url, markdown_format="gfm", extra_pandoc_args=None, md_path=None
):
    """
    Convert a single HTML file to Markdown using Pandoc.

    Args:
        html_path: Path to the input HTML file
        md_path: Path to the output Markdown file
        markdown_format: Markdown format to use (default: "gfm")
        extra_pandoc_args: Additional pandoc arguments as a list (default: None)

    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:

        # Read HTML content for preprocessing
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()

        # Preprocess HTML to include metadata from <div class="head">
        html_content = preprocess_html_for_metadata(html_content)

        # Base extra args for preserving code blocks and formatting
        # Note: fenced code blocks are enabled by default in gfm format
        base_extra_args = [
            "--wrap=none",  # Don't wrap lines
            "--preserve-tabs",  # Preserve tabs in code blocks
            "--standalone",
        ]

        # Add additional args if provided
        if extra_pandoc_args:
            if isinstance(extra_pandoc_args, str):
                base_extra_args.extend(extra_pandoc_args.split())
            else:
                base_extra_args.extend(extra_pandoc_args)

        # Convert HTML to Markdown using pandoc
        output = pypandoc.convert_text(
            html_content,
            markdown_format,
            format="html",
            extra_args=base_extra_args,
        )

        # Post-process the output to fix common issues
        output = post_process_markdown(output)
        url = check_url(url, output)
        output = "Source URL: " + url + "\n" + output

        # Ensure output directory exists
        if md_path:
            md_path.parent.mkdir(parents=True, exist_ok=True)
            # Write output to file
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(output)
        return output

    except pypandoc.pandoc.RuntimeError as e:
        # Pandoc-specific runtime error
        print(f"ERROR [Pandoc Runtime]: Failed to convert {html_path}")
        print(f"  Pandoc error: {str(e)}")
        return False
    except OSError as e:
        # System-level error (file not found, permissions, etc.)
        print(f"ERROR [System]: Failed to convert {html_path}")
        print(f"  System error: {str(e)}")
        print(f"  This is a system-level error (file access, permissions, etc.)")
        return False
    except UnicodeDecodeError as e:
        # Encoding error
        print(f"ERROR [Encoding]: Failed to convert {html_path}")
        print(f"  Encoding error: {str(e)}")
        print(f"  File may have invalid UTF-8 encoding or contain binary data")
        return False
    except Exception as e:
        # Other unexpected errors
        print(f"ERROR [Unexpected]: Failed to convert {html_path}")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        import traceback

        print(f"  Full traceback:")
        traceback.print_exc()
        return False


def check_url(url, output):
    """Check if the URL is valid"""
    words = url.split("/")
    new_url = []
    for idx, word in enumerate(words):
        page_name = "_".join([w for w in words[idx:] if w != ""])
        if page_name in output:
            new_url.append(page_name)
            break
        new_url.append(word)

    return "/".join(new_url)
