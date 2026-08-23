import json
import os
from pathlib import Path


def _incoming_counts(pages):
    """page_id -> number of buttons across the whole graph that href to it."""
    counts = {p.get("id"): 0 for p in pages}
    for p in pages:
        for b in p.get("buttons", []):
            href = b.get("href")
            if href in counts:
                counts[href] += 1
    return counts


def create_obsidian_library(json_file_path, output_dir="graph"):
    """
    Convert a JSON file with pages and buttons into Obsidian markdown files.

    Each note gets YAML frontmatter (page type, button/incoming-link counts,
    root/dead-end/orphan flags) so Obsidian's native Graph View can filter
    and color-code by tag instead of everything being one undifferentiated
    color. "back" buttons are now shown too (as non-navigable notes,
    previously silently dropped), so loops back to a hub page are visible
    in the graph instead of looking like dead ends.

    Args:
        json_file_path: Path to the JSON file
        output_dir: Directory to create the Obsidian library (default: "graph")
    """

    # Load the JSON data
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pages = data.get('pages', [])

    # Track all page IDs to validate links
    page_ids = {page.get('id') for page in pages}
    incoming = _incoming_counts(pages)

    # Create each page as a separate markdown file
    for page in pages:
        page_id = page.get('id', 'untitled')
        # Defensive: hand-authored pages.json entries (see PIPELINE.md — you
        # can add page objects by hand) may omit fields the tree scanner
        # always fills in. A missing 'title' used to raise KeyError and
        # abort the whole graph step instead of just this one note.
        title = page.get('title') or page_id
        buttons = page.get('buttons', [])
        message = page.get('message')
        page_type = page.get('type', 'standard')

        is_root = incoming.get(page_id, 0) == 0
        is_dead_end = bool(buttons) and all(
            b.get('href') in (None, '#') for b in buttons
        )
        is_back_only = bool(buttons) and all(b.get('href') == 'back' for b in buttons)
        is_orphan = page_id not in page_ids  # never true for real entries; kept for symmetry

        tags = [f"type/{page_type}"]
        if is_root:
            tags.append("root")
        if is_dead_end:
            tags.append("dead-end")
        if is_back_only:
            tags.append("back-only")

        # ── YAML frontmatter — drives Graph View color groups / Dataview ──
        content = ["---"]
        content.append(f"id: {page_id}")
        content.append(f"type: {page_type}")
        content.append(f"incoming-links: {incoming.get(page_id, 0)}")
        content.append(f"button-count: {len(buttons)}")
        content.append("tags: [" + ", ".join(tags) + "]")
        content.append("---\n")

        # Add title
        content.append(f"# {title}\n")

        # Add message if it exists and is not None/null
        if message and message.strip():
            content.append(f"{message}\n")

        # Add buttons section
        if buttons:
            content.append("## Buttons\n")

            # Sort buttons by layer to maintain order
            sorted_buttons = sorted(buttons, key=lambda x: x.get('layer', 0))

            for button in sorted_buttons:
                label = button.get('label', f"layer {button.get('layer', '?')}")
                href = button.get('href')
                icon = button.get('icon', '')
                layer = button.get('layer', '')
                transit = button.get('transit', [])
                btn_message = button.get('message')

                details = []
                if icon:
                    details.append(f"🔷 {icon}")
                if layer != '':
                    details.append(f"Layer: {layer}")
                if transit:
                    details.append(f"🎬 Transit: {', '.join(transit)}")

                if href == 'back':
                    # Previously skipped entirely — a page whose only exits
                    # are "back" rendered as if it had no buttons at all.
                    link_text = "↩ *(back)*"
                elif href and href in page_ids:
                    link_text = f"[[{href}|{label}]]"
                elif href:
                    # href doesn't resolve to a page — validate.py already
                    # errors on this, but show it here too so a broken link
                    # is visible right in the graph, not just in CI output.
                    link_text = f"⚠ **{label}** → broken href `{href}`"
                else:
                    link_text = f"— {label}" + (" 💬" if btn_message else "")

                if details:
                    content.append(f"- {link_text} *({', '.join(details)})*")
                else:
                    content.append(f"- {link_text}")

                if btn_message:
                    preview = btn_message.strip().replace("\n", " ")
                    if len(preview) > 80:
                        preview = preview[:77] + "…"
                    content.append(f"  - *VN: “{preview}”*")

        # Write the content to a markdown file
        output_file = output_path / f"{page_id}.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))

        print(f"Created: {output_file}")

    print(f"\n✅ Successfully created {len(pages)} pages in '{output_dir}/' directory")
    print("📁 You can now open this folder as an Obsidian vault!")
    print("   Graph View → Groups: try 'tag:#root', 'tag:#dead-end', 'tag:#type/slideshow'")

# Usage
if __name__ == "__main__":
    # Specify your JSON file path here
    json_file = "pages.json"  # Change this to your JSON file path
    
    # Check if file exists
    if not os.path.exists(json_file):
        print(f"❌ Error: Could not find '{json_file}'")
        print("Please update the 'json_file' variable with the correct path to your JSON file")
    else:
        # Create the Obsidian library
        create_obsidian_library(json_file, output_dir="graph")