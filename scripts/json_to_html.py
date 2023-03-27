import json
import sys
from typing import Any

line_map = {
    'Paragraph':'p',
    'H1':'h1',
    'H2':'h2',
    'H3':'h3',
    'H4':'h4',
    'Emphasis':'p',
}

def line_to_html(text: Any):
    line_text = ""
    for span in text['spans']:
        style = f"color:#{span['font']['colour']}"
        span_text = span['text']
        if span['font']['bold']:
            span_text = f"<b>{span_text}</b>"
        if span['font']['italic']:
            span_text = f"<i>{span_text}</i>"
        
        line_text += f"<div style=\"{style}\">{span_text}</div>"
    return line_text

def text_to_html(text: Any):
    if text['variant'] in line_map:
        variant = line_map[text['variant']]
    else:
        variant = 'p'

    text = f"<{variant}>" + "</br>".join(line_to_html(line) for line in text['items']) + f"</{variant}>"
    return text


def item_to_html(item: Any):
    if item['name'] == 'textblock':
        return text_to_html(item)
    
    return ""

def json_to_html(json: Any):
    full_content = ""
    for page_number in json:
        data = json[page_number]
        content = "".join(item_to_html(i) for i in data)
        full_content += f"<div>{content}</div>"
    return full_content

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ERROR: Expect single json filename as argument")

    file = sys.argv[1]
    with open(file, 'r') as f:
        data = json.load(f)
        print(json_to_html(data['json']))
