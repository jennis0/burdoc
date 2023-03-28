import argparse
import json
import os
from typing import Any, Dict, List

line_map = {
    'Paragraph':'p',
    'H1':'h1',
    'H2':'h2',
    'H3':'h3',
    'H4':'h4',
    'Emphasis':'p',
}

def cell_to_html(cell: List[Dict[str, Any]]) -> str:
    """Turns table cell into HTML

    Args:
        cell (List[Dict[str, Any]])

    Returns:
        str: HTML
    """
    return ' '.join([item_to_html(e) for e in cell])

def table_to_html(table: Dict[str, Any]) -> str:
    """Turns table into HTML table

    Args:
        table (Dict[str, Any])

    Returns:
        str: HTML
    """
    text = "<table>"
    
    #For now, only consider first column header. More complex table parsing to come!
    skip_rows = set()
    if 'col_header_index' in table and len(table['col_header_index']) >0 and table['col_header_index'][0] == 0:
        header = "<theader>"
        header += "".join([f"<th>{cell_to_html(cell)}</th>" for cell in table['cells'][0]])
        header += "</theader>"
        text += header
        skip_rows.add(0)
    
    for i,row in enumerate(table['cells']):
        if i in skip_rows:
            continue
        cell_text = "".join([f"<td>{cell_to_html(cell)}</td>" for cell in row])
        text += f"<tr>{cell_text}</tr>"
    text += "</tbody></table>"

    return text

def aside_to_html(aside: Dict[str, Any]) -> str:
    """Turns asides into grey-background boxes

    Args:
        aside (Dict[str, Any])

    Returns:
        str: HTML
    """
    item_text = "".join(item_to_html(i) for i in aside['items'])
    return f"<div style='background-color:grey'>{item_text}</div>"

def textlist_item_to_html(textlist_item: Dict[str, Any], style_type: str) -> str:
    """Turns textlist item into <li>

    Args:
        textlist_item (Dict[str, Any]): textlist_item
        style_type (str): sets 'list-style-type'

    Returns:
        str: HTML
    """
    item_text = ''.join(f'<p>{text_to_html(e)}</p>' for e in textlist_item['items'])
    return f"<li style=\"list-style-type:{style_type}\">{item_text}</li>"

def textlist_to_html(textlist: Dict[str, Any]) -> str:
    """Turns textlist into <ol> or <ul>

    Args:
        textlist (Dict[str, Any])

    Returns:
        str: HTML
    """
    if textlist['ordered']:
        list_type = "ol"
        if str.isnumeric(textlist['items'][0]['label']):
            style_type = "decimal"
        elif str.islower(textlist['items'][0]['label']):
            style_type = "lower-alpha"
        elif str.isupper(textlist['items'][0]['label']):
            style_type = "upper-alpha"
    else:
        list_type = "ul"
        style_type = "circle"
        
    item_text = "".join([textlist_item_to_html(item, style_type) for item in textlist['items']])
    return f"<{list_type}>{item_text}</{list_type}>"

def line_to_html(text: Dict[str, Any]) -> str:
    """Turns line into row of <span>

    Args:
        text (Dict[str, Any])

    Returns:
        str: HTML
    """
    line_text = ""
    for span in text['spans']:
        style = f"color:#{span['font']['colour']}"
        span_text = span['text']
        if span['font']['bold']:
            span_text = f"<b>{span_text}</b>"
        if span['font']['italic']:
            span_text = f"<i>{span_text}</i>"
        
        line_text += f"<span style=\"{style}\">{span_text}</span>"
    return line_text

def text_to_html(text: Dict[str, Any]) -> str:
    """Turns textblock into <p>

    Args:
        text (Dict[str, Any])

    Returns:
        str: HTML
    """
    if text['type'] in line_map:
        text_type = line_map[text['type']]
    else:
        text_type = 'p'
    
    html_text = f"<{text_type}>" + "".join(line_to_html(line) for line in text['items']) + f"</{text_type}>"
    return html_text


def item_to_html(item: Dict[str, Any]) -> str:
    """Routes an item to the correct HTML generator based on 'name' attribute

    Args:
        item (Dict[str, Any])

    Returns:
        str: Dict[str, Any]
    """
    if item['name'] == 'textblock':
        return text_to_html(item)
    
    if item['name'] == 'line':
        return line_to_html(item)
    
    if item['name'] == 'aside':
        return aside_to_html(item)
    
    if item['name'] == 'textlist':
        return textlist_to_html(item)
    
    if item['name'] == 'table':
        return table_to_html(item)
    
    return ""

def json_to_html(json_data: Dict[str, Any]) -> str:
    """Converts the 'content' portion of an extraction into HTML

    Args:
        json (Dict[str, Any])

    Returns:
        str: HTML
    """
    full_content = ""
    for page_number in json_data:
        data = json_data[page_number]
        content = "".join(item_to_html(i) for i in data)
        full_content += f"<div><h1>Page={page_number}</h1><div style='max-width:600px'>{content}</div></div>"
    return full_content


def run():
    """Reads an input file and either generates an output or dumps it to the terminal

    Raises:
        FileNotFoundError: Input file not found
    """
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--in-file", "-i", type=str, help="Input JSON file", required=True)
    argparser.add_argument("--out-file", "-o", type=str, required=False, help="File to write HTML to")
    
    args = argparser.parse_args()
    if not os.path.exists(args.in_file):
        raise FileNotFoundError(args.in_file)
    
    with open(args.in_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    html = json_to_html(data['content'])
    
    if args.out_file:
        with open(args.out_file, 'w', encoding='utf-8') as f:
            f.write(html)
    else:
        print(html)
            
        

if __name__ == "__main__":
    run()
