import argparse
import json
import os
import numpy as np
from yattag import Doc
from typing import Any, Dict, Tuple, List

from burdoc.utils.json_to_html import JsonHtmlConverter


def make_anchor_name(text: str) -> str:
    """Creates a consistent anchor name from a piece of text by replacing spaces with 
    '-' and limiting to 12 characters.

    Args:
        text (str): Source text

    Returns:
        str: Anchor name
    """
    return text.replace(" ", "-")[:12]


def get_head(title):
    text = "<head>"
    text += f"<title>{title}</title>"
    text += "<style>"
    text += "table {border-collapse: collapse; margin: 25px 0; font-size: 0.9em;"
    text += "font-family: sans-serif;  min-width: 400px;}"
    text += "td {padding: 5px 6px;}"
    text += "th {padding: 6px 6px; text-align: left;}"
    text += "tbody tr {border-bottom: 1px solid #dddddd}"
    text += "table tbody tr:nth-of-type(even) {background-color: #f3f3f3;}"
    text += "table tbody tr:last-of-type {border-bottom: 2px solid #c4c4c4;}"
    text += "table tbody tr:first-of-type {border-top: 2px solid #c4c4c4;}"
    text += "h1, h2, h3, h4, h5, p, a {font-family: arial;}"
    text += "li {padding: 4px 3px}"
    text += ".collapsible {background-color: #5a5a5a; color: white; cursor: pointer; padding:10px; width:100%;"
    text += "border:none; text-align:left; outline:none; font-size:12pt; margin-bottom:5pt}"
    text += ".active .collabsible:hover {background-color:#1a1a1a}"
    text += ".content {padding: 0 10px; display:none; overflow: hidden; background-color:#fafafa}"
    text += "</style>"
    text += "</head>"
    return text


def get_font_table(font_data):
    doc, tag, text, line = Doc().ttl()
    with tag('div'):
        with tag('table'):
            with tag('theader'):
                line('th', 'Font Name')
                line('th', 'Size')
                line('th', 'Count')
                line('th', 'Bold')
                line('th', 'Italic')
                line('th', 'Superscript')
                line('th', 'Small Caps')
                line('th', 'True Sizes')
            with tag('tbody'):
                for family in font_data:
                    with tag('tr'):
                        line('th', family)
                        line('th', '')
                        line('th', '')
                    for fontname, font in font_data[family].items():
                        if fontname == "_counts":
                            continue
                        for size, size_count in font['counts'].items():
                            with tag('tr'):
                                line('td', fontname)
                                line('td', size)
                                line('td', size_count)
                                
                                if 'data' in font:
                                    line('td', font['data']['bd'])
                                    line('td', font['data']['it'])
                                    line('td', font['data']['sp'])
                                    line('td', font['data']['sc'])
                                else:
                                    line('td', '?')
                                    line('td', '?')
                                    line('td', '?')
                                    line('td', '?')
                                
                                if 'true_sizes' in font and size in font['true_sizes']:
                                    vals = font['true_sizes'][size]
                                    line('td', f"Mean={round(np.mean(vals), 1)} | Min={round(np.min(vals), 1)}"+\
                                        f" | Max={round(np.max(vals), 1)} | Var={round(np.var(vals), 1)}")
                                    
    return get_collapsible(doc.getvalue(), 'Fonts')


def get_collapsible(content, title, background=None, content_background=None):
    doc, tag, _, line = Doc().ttl()

    if not background:
        line('button', title, klass='collapsible')
    else:
        line('button', title, klass='collapsible',
             style=f'background-color:{background}')

    if content_background:
        with tag('div', klass='content', style=f"background-color:{content_background}"):
            doc.asis(content)
    else:
        with tag('div', klass='content'):
            doc.asis(content)

    return doc.getvalue()


def get_scripts():

    text = """
    <script>
        var coll = document.getElementsByClassName("collapsible");
        var i;

        for (i = 0; i < coll.length; i++) {
        coll[i].addEventListener("click", function() {
            this.classList.toggle("active");
            var content = this.nextElementSibling;
            if (content.style.display === "block") {
            content.style.display = "none";
            } else {
            content.style.display = "block";
            }
        });
        }
    </script>"""
    return text


def get_metadata_table(metadata: Dict[str, Any], pages: List[str]) -> str:
    """Creates a table showing metadata extracted from the document

    Args:
        metadata (Dict[str, Any]): _description_
        pages (List[int]): _description_

    Returns:
        str: _description_
    """
    doc, tag, text, line = Doc().ttl()

    pages.sort()
    with tag('div'):
        with tag('table'):
            with tag('tr'):
                line('th', 'Title')
                line('td', metadata['title'])
            with tag('tr'):
                line('th', 'Path')
                line('td', os.path.abspath(metadata['path']))
            with tag('tr'):
                line('th', 'Pages')
                line('td', ",".join(pages))

            for key in metadata['pdf_metadata']:
                with tag('tr'):
                    line('th', f"PDF Metadata: {key}")

                    value = metadata['pdf_metadata'][key]
                    line('td', value if value else "")

    return get_collapsible(doc.getvalue(), 'Metadata')


def get_toc_list(page_hierarchy: Dict[str, Any]) -> str:
    """Creates a table of content with links for quickly jumping to the page

    Args:
        page_hierarchy (Dict[str, Any]): Page hierarchy to build the ToC from

    Returns:
        str: An HTML list
    """
    doc, tag, text, line = Doc().ttl()

    with tag('div'):
        line('h2', 'Contents', style='margin-bottom:1pt;', id='-contents')
        with tag('ol', style='margin-top:0pt'):
            for page in page_hierarchy:
                with tag('li'):
                    with tag('a', style='font-size:12pt', href=f'#anchor-page-{page}'):
                        text(f'Page {page}')
                    
                for item in page_hierarchy[page]:
                    with tag('li'):
                        with tag('a', href=f"#{page}-{make_anchor_name(item['text'])}"):
                            text(f"{item['assigned_heading']} :: {item['text']}")


    return get_collapsible(doc.getvalue(), 'Contents')


def get_embed(json_data: Dict[str, Any]):
    return f"<object><embed src=\"{'file://' + os.path.abspath(json_data['metadata']['path'])}\" style='width:80%; border:none; height:95%' ></object>"


def get_images(json_data: Dict[str, Any]):

    doc, tag, text, line = Doc().ttl()
    if 'images' in json_data:
        with tag('div', style='padding-bottom:10pt'):
            for page in json_data['images']:
                line('h4', f'Page {page}')
                for image_data in json_data['images'][page]:
                    doc.stag('img', src=f"data:image/webp;base64, {image_data}",
                             style='margin:10pt; max-height:200pt; max-width:45%')
                    
                if len(json_data['images'][page]) == 0:
                    with tag('div'):
                        text('No images')

        return get_collapsible(doc.getvalue(), "Images")
    return ""


def create_top_links(links: Dict[str, str]) -> str:

    text = "<div style='padding:5pt; width:100%'>"
    text += '&nbsp'.join(
        f'<a href=\"{links[link]}\" style="font-size:15"><b>{link}</b></a>' for link in links)
    text += '<hr></div>'
    return text

def get_value_rep(content, depth=0):
    doc, tag, text, line = Doc().ttl()

    if depth > 3:
        text(str(content))
        return doc.getvalue()

    if isinstance(content, dict):
        with tag('table', style='margin:1pt; padding:1pt'):
            with tag('theader'):
                line('th', 'Key')
                line('th', 'Value')
            with tag('tbody'):
                for k,item in content.items():
                    with tag('tr'):
                        line('th', k)
                        with tag('td'):
                            doc.asis(get_value_rep(item, depth+1))
    elif isinstance(content, list):
        with tag('table'):
            with tag('tbody'):
                for item in content:
                    with tag('tr'):
                        with tag('td'):
                            doc.asis(get_value_rep(item, depth+1))
                        
    else:
        text(str(content))
    return doc.getvalue()

def json_to_table(old_content, new_content):
    doc, tag, _, line = Doc().ttl()
    
    oct = type(old_content)
    nct = type(new_content)
    
    if not old_content:
        old_content = nct()
    if not new_content:
        new_content = oct()
    
    with tag('table', style='margin:2pt; padding:2pt'):
        with tag('theader'):
            if isinstance(old_content, dict):
                line('th', 'Key')
            line('th', 'Old')
            line('th', 'New')
            
        with tag('tbody'):
            
            if isinstance(old_content, dict):
                keys = list(set(old_content.keys()).union(new_content.keys()))
                for key in keys:
                    with tag('tr'):
                        line('th', key)
                        if key in old_content:
                            with tag('td'):
                                doc.asis(get_value_rep(old_content[key]))
                        else:
                            line('td', '')
                        if key in new_content:
                            with tag('td'):
                                doc.asis(get_value_rep(new_content[key]))
                        else:
                            line('td', '')
                            
            elif isinstance(old_content, list):
                if len(new_content) < len(old_content):
                    new_content += [None]*(len(old_content) - len(new_content))
                if len(old_content) < len(new_content):
                    old_content += [None]*(len(new_content) - len(old_content))
                for i1, i2 in zip(old_content, new_content):
                    with tag('tr'):
                        with tag('td'):
                            doc.asis(get_value_rep(i1))
                        with tag('td'):
                            doc.asis(get_value_rep(i2))
                        
            else:
                with tag('tr'):
                    with tag('td'):
                        doc.asis(get_value_rep(old_content))
                    with tag('td'):
                        doc.asis(get_value_rep(new_content))

    return doc.getvalue()
                        
                        

def get_change_view(changes: List[Dict[str, Any]]):
    doc, tag, text, line = Doc().ttl()

    with tag('div'):
        for c in changes:
            with tag('div', style='margin-bottom:10pt'):
                with tag('table', style='padding:1pt; margin:1pt; font-size:12pt'):
                    with tag('tr'):
                        line('th', 'Path:')
                        line('td', c['path'])
                    with tag('tr'):
                        line('th', 'Type:')
                        line('td', c['type'])
                        
                    if c['type'] == 'reorder':
                        with tag('tr'):
                            line('th', 'Old Pos')
                            line('td', c['old'])
                        with tag('tr'):
                            line('th', 'New Pos')
                            line('td', c['new'])

                if 'value' in c:
                    doc.asis(get_collapsible(get_value_rep(c['value']), 'Value'))
                    doc.stag('hr')
                    continue
                    
                new = c['new'] if 'new' in c else None
                old = c['old'] if 'old' in c else None
                doc.asis(get_collapsible(json_to_table(old, new), 'Change'))
                doc.stag('hr')

    return doc.getvalue()


def create_embedded_view(
    links: Dict[str, str],
    html_pages: Dict[str, Any],
    gold_pages: Dict[str, Any],
    report: Dict[str, Any],
    json_data: Dict[str, Any]
) -> str:
    doc, tag, _, line = Doc().ttl()

    doc.asis(get_head(json_data['metadata']['title']))
    with tag('body'):
        with tag('div', style='height:98%; padding:0pt; margin:0pt'):
            with tag('div',
                    style='width:50%; overflow-y:scroll; height:100%; padding:20pt; float: left'):
                line('h2', 'Metadata')
                doc.asis(get_metadata_table(
                    json_data['metadata'], list(json_data['content'].keys())))
                
                if 'font_statistics' in json_data['metadata']:
                    doc.asis(get_font_table(json_data['metadata']['font_statistics']))
                doc.asis(get_toc_list(json_data['page_hierarchy']))
                doc.asis(get_images(json_data))
                doc.stag("hr")

                for page in html_pages:

                    page_changes = [c for c in report['changes']
                                    if f'content.{page}' in c['path'] and 'font' not in c['path']]
                    if len(page_changes) > 0:
                        col = '#ff5050'
                    else:
                        col = 'lightblue'

                    line(
                        'button', f"Page {page}", klass='collapsible', style=f'background-color:{col};')
                    with tag('div', klass='content'):
                        if len(page_changes) > 0:
                            doc.asis(get_collapsible(get_change_view(page_changes),
                                                    'Changes', background="#909090"))
                        doc.asis(get_collapsible(
                            html_pages[page], f'New Page {page}', background=col))
                        doc.asis(get_collapsible(
                            gold_pages[page], f'Gold Page {page}', background="gold"))
                        

            with tag('div', style='margin:0, padding:0; height:100%; width:45%; float:left'):
                links['Contents'] = '#-contents'
                doc.asis(create_top_links(links))
                del links['Contents']
                with tag('div'):
                    doc.asis(get_embed(json_data))

        doc.asis(get_scripts())
    return doc.getvalue()


def create_directory_view(in_path: str, path_stem: str, links: Dict[str, str],
                          report: Dict[str, Any], scores: Dict[str, Tuple[int, str]]):
    files = [[os.path.join(path_stem, f), f] for f in os.listdir(in_path) if f.endswith(
        ".html") or os.path.isdir(os.path.join(in_path, f))]

    for file in files:
        if '.' in file[0]:
            file[0] = ".".join(file[0].split('.')[:-1])
        if not file[1].endswith(".html"):
            file[1] = os.path.join(file[1], "index.html")

    score_colour_map = {
        0: "darkgrey", 1: "darkred", 2: "red", 3: "orange", 4: "lightgreen", 5: "green"
    }

    text = get_head(path_stem)
    text += f"<body><div style='padding:5pt'><h2>{in_path}</h2><div>"

    text += "<h4>Links</h4><ul>"
    for l in links:
        text += f"<a href=\"{links[l]}\">{l}</a>"

    text += "</ul></div><div><h4>Navigation</h4>"

    text += "<table style='font-size:12pt; text-align:center'><theader><th>Pass</th><th>File</th><th>Added</th>"
    text += "<th>Removed</th><th>Changes</th><th>Reordered</th><th>Score</th><th>Comments</th></theader>"
    text += "<tbody>"
    for name, path in files:
        if name == "index":
            continue

        if name in report['files']:

            result = report['files'][name]

            total_changes = len([c for c in result['changes'] if c['path'].startswith("content.") and not 'font' in c['path']])

            adds = len([c for c in result['changes']
                       if c['type'] == 'addition'])
            dels = len([c for c in result['changes']
                       if c['type'] == 'deletion'])
            reorders = len([c for c in result['changes']
                           if c['type'] == 'reorder'])
            change_count = len(
                [c for c in result['changes'] if c['type'] == 'change'])

            if total_changes == 0:
                tick = '&check;'
                colour = 'green'
            elif total_changes > 0 and scores[name][0] >= 4:
                tick = '&#10006;'
                colour = 'red'
            else:
                tick = '&#9888;'
                colour = 'orange'

            score = scores[name][0]
            comment = scores[name][1]
            score_colour = score_colour_map[score]

            name = os.path.basename(name)

            text += f"<tr><th style='background-color:{colour}; text-align:center; color:#fafafa; font-size:14pt'>{tick}</th>"
            text += f"<td><a href=\"{path}\">{name}</a></td>"
            text += f"<td>{adds}</td><td>{dels}</td><td>{change_count}</td><td>{reorders}</td>"
            text += f"<th style='background-color:{score_colour}; text-align:center; color:#fafafa; font-size:14pt'>{score}</th>"
            text += f"<td>{comment}</th>"
            text += "</tr>"

        else:

            dirname = os.path.dirname(name)
            if dirname != "":
                name = dirname

            if name == path_stem:
                continue

            dir_files = [f for f in report['files'].keys()
                         if f.startswith(name)]
            changes = [0, 0]

            for df in dir_files:
                change_count = len(report['files'][df]['changes'])
                score = scores[df][0]
                if score >= 4:
                    changes[0] += change_count
                else:
                    changes[1] += change_count

            if changes[0] > 0:
                tick = '&#10006;'
                colour = 'red'
            elif changes[1] > 0:
                tick = '&#9888;'
                colour = 'orange'
            else:
                tick = '&check;'
                colour = 'green'

            print(path, name)

            text += f"<tr><th style='background-color:{colour}; text-align:center; color:#fafafa; font-size:14pt'>{tick}</th>"
            text += f"<td><a href=\"{path}\">{name}/</a></td><td></td><td></td><td></td><td></td>"
            text += f"<th style='background-color:darkgrey; font-size:14pt'></th><td></td>"

            text += "</tr>"

    text += "</tbody></table>"
    text += "</div></div>"
    return text


def parse_path(converter: JsonHtmlConverter,
               in_path: str, out_path: str, gold_path: str,
               path: str,
               report: Dict[str, Any], scores: Dict[str, Tuple[int, str]],
               links: Dict[str, str]):

    target_path = os.path.join(in_path, path)
    gold_target_path = os.path.join(gold_path, path)
    target_out_path = os.path.join(out_path, path)
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"{target_path} does not exist")

    if os.path.isdir(target_path):

        if not os.path.exists(target_out_path):
            os.makedirs(target_out_path)

        last_parent = links['Parent']
        index_path = os.path.join(target_out_path, 'index.html')
        links['Parent'] = "file://" + os.path.abspath(index_path)

        for filename in os.listdir(target_path):
            new_path = os.path.join(path, filename)
            parse_path(converter, in_path, out_path, gold_path,
                       new_path, report, scores, links)

        links["Parent"] = last_parent
        index = create_directory_view(
            target_out_path, path, links, report, scores)
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index)

    else:
        target_out_path = target_out_path.replace(".json", ".html")
        with open(target_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with open(gold_target_path, 'r', encoding='utf-8') as f:
            gold_data = json.load(f)
        
        links['File'] = "file://" + os.path.abspath(target_path)

        html_pages = {page_number: converter.convert_page(data, page_number, False, False)
                    for page_number in data['content'].keys()}
        gold_pages = {page_number: converter.convert_page(gold_data, page_number, False, False)
                    for page_number in data['content'].keys()}
    
        html = create_embedded_view(links, html_pages, gold_pages,
                                    report['files'][".".join(path.split(".")[:-1])], data)

        del links['File']

        with open(target_out_path, 'w', encoding='utf-8') as f:
            f.write(html)



def run():
    """Reads an input file and either generates an output or dumps it to the terminal

    Raises:
        FileNotFoundError: Input file not found
    """
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "report", type=str, help="Output report of a test run")
    args = argparser.parse_args()

    with open(args.report, 'r', encoding='utf-8') as f:
        report = json.load(f)

    in_dir = report['out_dir']
    out_dir = os.path.join(
        os.path.dirname(args.report), 'html')

    gold_dir = os.path.join(
        os.path.dirname(args.report), 'gold')

    scores_path = os.path.join(
        os.path.dirname(args.report), 'scores.json')

    if os.path.exists(scores_path):
        write_scores = False
        with open(scores_path, 'r', encoding='utf-8') as f:
            scores = json.load(f)
    else:
        write_scores = True
        scores = {f: [0, ""] for f in report['files'].keys()}

    if not os.path.exists(in_dir):
        raise FileNotFoundError(in_dir)

    converter = JsonHtmlConverter()

    parse_path(converter, in_dir, out_dir, gold_dir, '', report, scores, {
               'Parent': "file://" + os.path.join(os.path.abspath(out_dir), 'index.html')})

    if write_scores:
        with open(scores_path, 'w', encoding='utf-8') as f:
            json.dump(scores, f)
            
    print(f"Written index to {os.path.abspath(os.path.join(out_dir, 'index.html'))}")


if __name__ == "__main__":
    run()
