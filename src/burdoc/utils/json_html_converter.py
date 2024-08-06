"""Convert JSON output into HTML"""

from typing import Any, Dict, List, Optional, Sequence
import re


def check_if_header_and_fix(item, toc_items):
    if 'type' in item:
        if item['type'] in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = item['block_text'].lower()

            if text in toc_items:
                item['type'] = "h" + str(toc_items[text])
                
    if item['name'] == "aside":
        for new_item in item['items']:
            check_if_header_and_fix(new_item, toc_items)

def fix_header_format(toc, content):
        
    page_toc = {}
    for item in toc:
        if item[2] - 1 in page_toc:
            page_toc[item[2] - 1].append([item[0], item[1].lower(), item[2]])
        else:
            page_toc[item[2] - 1] = [[item[0], item[1].lower(), item[2]]]
                                    
    for page,page_items in content.items():
        
        page = int(page)
        if page not in page_toc:
            continue
        
        toc_items = {pt[1]:pt[0] for pt in page_toc[page]}

        for item in page_items:
            check_if_header_and_fix(item, toc_items)
         

class JsonHtmlConverter():
    '''Converts Burdoc JSON output into HTML'''

    line_map = {
        'paragraph': 'p',
        'h1': 'h1',
        'h2': 'h2',
        'h3': 'h3',
        'h4': 'h4',
        'h5': 'h5',
        'h6': 'h6',
        'emphasis': 'p',
        'small': 'p'
    }

    def __init__(self, split: List[str]=['page'], css: Optional[str]=None, classes: Dict[str, str]={}):
        self.images: Optional[Dict[str, Sequence[str]]] = None
        self.current_page = 0
        
        self.split = split
        self.classes = classes
        self.split_marker = "#£!"
                        
        if not css:
            self.css = """
        table {
            border-collapse: collapse; margin: 25px 0; min-width: 400px;
            font-size: 0.9em; font-family: sans-serif;
        }
        td {padding: 5px 6px;}
        th {padding: 6px 6px; text-align: left;}
        tbody tr {border-bottom: 1px solid #dddddd;}
        table tbody tr:nth-of-type(even) {background-color: #f3f3f3;}
        table tbody tr:last-of-type {border-bottom: 2px solid #c4c4c4;}
        table tbody tr:first-of-type {border-top: 2px solid #c4c4c4;}
        h1, h2, h3, h4, h5, p, a {font-family: arial;}
        li {padding: 4px 3px}
        """
        else:
            self.css = css
        

        self.route_dict = {
            'textblock': self._text_to_html,
            'line': self._line_to_html,
            'aside': self._aside_to_html,
            'textlist': self._textlist_to_html,
            'table': self._table_to_html,
            'image': self._image_to_html
        }

    def _cell_to_html(self, cell: List[Dict[str, Any]]) -> str:
        """Turns table cell into HTML

        Args:
            cell (List[Dict[str, Any]])

        Returns:
            str: HTML
        """
        return ' '.join([self._item_to_html(e) for e in cell])

    def _tag(self, tag: str, children: str=None, 
             tag_class: Optional[str]=None,
             additional_args: Dict[str, str]={}
             ) -> str:
        '''Returns an HTML tag with optional class data added from configuration
        tag [str] - HTML tag
        children [str] - Children of the HTML tag
        tag_class Optional[str] - Tag class to reference, uses tag if not set
        additional_args: Dict[str, str] - Any additional options to be passed into the HTML tag
        Returns: An HTML tag with classes
        '''
        
        if not tag_class:
            tag_class = tag
            
        if tag in self.split:
            fragment = f"{self.split_marker}<{tag}"
        else:
            fragment = f"<{tag}"
        
        for k in additional_args:
            fragment += " " + f"{k}=\"{additional_args[k].strip()}\"" 
        
        if tag_class in self.classes and self.classes[tag_class]:
            fragment = fragment + " " + 'class="' + self.classes[tag_class] + '"'
            
        if children:
            fragment += ">" + children + f"</{tag}>"
        else:
            fragment += "/>"
        
        return fragment

    def _table_to_html(self, table: Dict[str, Any]) -> str:
        """Turns table into HTML table

        Args:
            table (Dict[str, Any])

        Returns:
            str: HTML
        """
        text = self._tag("table", "table")

        # For now, only consider first column header. More complex table parsing to come!
        skip_rows = set()
        header = ""
        if 'col_header_index' in table and len(table['col_header_index']) > 0 and table['col_header_index'][0] == 0:
            if len(table['cells']) > 0:
                for cell in table['cells'][0]:
                    child = self._cell_to_html(cell)
                    header += self._tag("th", child)

            header = self._tag("theader", header)
            skip_rows.add(0)

        body = ""
        for i, row in enumerate(table['cells']):
            if i in skip_rows:
                continue
            cell_text = "".join(
                [self._tag("td", self._cell_to_html(cell)) for cell in row])
            body += self._tag("tr", cell_text)
        body = self._tag("tbody", body)
        
        return self._tag("table", header + body)

    def _aside_to_html(self, aside: Dict[str, Any]) -> str:
        """Turns asides into grey-background boxes

        Args:
            aside (Dict[str, Any])

        Returns:
            str: HTML
        """
        item_text = "".join(self._item_to_html(i) for i in aside['items'])
        return self._tag("div", item_text, tag_class="aside")

    def _textlist_item_to_html(self, textlist_item: Dict[str, Any], style_type: str) -> str:
        """Turns textlist item into <li>

        Args:
            textlist_item (Dict[str, Any]): textlist_item
            style_type (str): sets 'list-style-type'

        Returns:
            str: HTML
        """
        item_text = ''.join(
            self._text_to_html(e) for e in textlist_item['items']
        )
        return self._tag("li", item_text, additional_args={'list-style-type':style_type})

    def _textlist_to_html(self, textlist: Dict[str, Any]) -> str:
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

        item_text = "".join([self._textlist_item_to_html(item, style_type)
                            for item in textlist['items']])
        return self._tag(list_type, item_text)

    def _line_to_html(self, text: Dict[str, Any]) -> str:
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

            if len(span_text) == 0:
                continue
            
            if span['font']['sc']:
                span_text = span_text.upper()
            if span['font']['bd']:
                span_text = self._tag("b", span_text)
            if span['font']['it']:
                span_text = self._tag("i", span_text)
        
            line_text += self._tag("span", span_text, additional_args={'style':style})

        return line_text

    def _make_anchor_name(self, text: str) -> str:
        """Creates a consistent anchor name from a piece of text by replacing spaces with 
        '-' and limiting to 12 characters.

        Args:
            text (str): Source text

        Returns:
            str: Anchor name
        """
        if isinstance(text, str):
            return text.strip().replace(" ", "-")[:12]
        
        if isinstance(text, set):
            return list(text)[0].strip().replace(" ", "-")[:12]


    def _text_to_html(self, text: Dict[str, Any]) -> str:
        """Turns textblock into <p>

        Args:
            text (Dict[str, Any])

        Returns:
            str: HTML
        """
        if text['type'] in JsonHtmlConverter.line_map:
            text_type = JsonHtmlConverter.line_map[text['type']]
        else:
            text_type = 'p'

        if text_type in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            additional_args = {
                "id":f"{self.current_page}-{self._make_anchor_name({text['block_text']})}"
            }
        else:
            additional_args = {}

        html_text = self._tag(
            text_type,
            "".join(self._line_to_html(line) for line in text['items']),
            additional_args=additional_args
        )
        return html_text

    def _image_to_html(self, image: Dict[str, Any]) -> str:
        
        if not self.images:
            return ""
            #return self._tag("div", self._tag("h2", "MISSING IMAGE"))
        
        if image['image'] < len(self.images[self.current_page]):
            image_data = self.images[self.current_page][image['image']]
            return self._tag("img", image_data, 
                             additional_args={'src':"data:image/webp;base64", 
                                              "style":"max-width:45%; max-height:300pt"}
                             )
        else:
            return self._tag("div", self._tag("h2", "MISSING IMAGE"))

    def _item_to_html(self, item: Dict[str, Any]) -> str:
        """Routes an item to the correct HTML generator based on 'name' attribute

        Args:
            item (Dict[str, Any])

        Returns:
            str: Dict[str, Any]
        """
        
        if not item or item['name'] == "empty":
            return ""

        if item['name'] in self.route_dict:
            return self.route_dict[item['name']](item)

        raise RuntimeError(
            f"Couldn't find HTML parser for item type \'{item['name']}\'")



    def _get_head(self, json_data):
        head = self._tag("title", json_data['metadata']['title'])
        head += self._tag("style", self.css)
        return self._tag("head", head)

    def convert_elements(self, elements: List[Any]) -> str:
        """Converts an arbitrary list of elements from Burdoc JSON output into HTML
        Args:
            elements: A list of JSON elements from Burdoc
        Returns:
            str: HTML representation of those elements wrapped in a div
        """
        return self._tag("div", "".join(self._item_to_html(element) for element in elements))

    def convert_page(self, json_data: Dict[str, Any],
            page_number: int,
            insert_page_tags: bool = True,
            insert_head: bool = True) -> str:
        """Converts a single page from Burdoc JSON output into HTML.

        Args:
            json_data (Dict[str, Any]): The JSON output from Burdoc
            page_number (int): Page number to extract
            insert_page_tags (bool, optional): Whether to insert prominent page labels at
                the start of each page. Defaults to True.
            insert_head (bool, optional): Include a <head> tag with style information

        Returns:
            str: HTML representation of the page
        """
        
        if 'images' in json_data:
            self.images = json_data['images']
            
        self.current_page = page_number
        content = "".join(self._item_to_html(i) for i in json_data['content'][page_number])
        
        if insert_page_tags:
            body = self._tag("h1", f"Page {page_number}", additional_args={'id':f'anchor-page-{page_number}'}) +\
                   self._tag("hr") +\
                   self._tag("div", content, additional_args={'style':'max-width:1000px'})
        elif self.split == "page":
            body = self._tag("div", content, additional_args={'id':f'anchor-page-{page_number}'})
        else:
            body = content
            
        
        if insert_head:
            full_content = self._get_head(json_data) + self._tag("body", body)
        else:
            full_content = body
            
        return full_content

        



    def convert(self, json_data: Dict[str, Any],
                insert_page_tags: bool = True,
                insert_head: bool = True) -> str:
        """Converts Burdoc JSON output into HTML.

        Args:
            json_data (Dict[str, Any]): The JSON output from Burdoc
            insert_page_tags (bool, optional): Whether to insert prominent page labels at
                the start of each page. Defaults to True.
            insert_head (bool, optional): Include a <head> tag with style information

        Returns:
            str: HTML representation of the passed data
        """

        if 'images' in json_data:
            self.images = json_data['images']
            
        fix_header_format(json_data['metadata']['toc'], json_data['content'])
        
        id_regex = re.compile("id=\"(.*?)\"")

        body = []
        temp_body = []
        for page_number in json_data['content']:
            
            if self.split == 'page':
                temp_body.append("")
            
            page_content = self.convert_page(json_data, page_number, insert_page_tags, False)
            page_content_parts = page_content.split(self.split_marker)
                
            if len(page_content_parts) == 1 and page_content_parts[0] == '':
                continue
            
            if len(temp_body) > 0 and page_content_parts[0].strip() != '':
                if len(page_content_parts) == 1:
                    temp_body[-1] += page_content_parts[0]
                    continue
                
                else:
                    temp_body[-1] += page_content_parts[0]
                    page_content_parts = page_content_parts[1:]
                    
            if page_content_parts[0] == '':
                page_content_parts = page_content_parts[1:]
                
            for part in temp_body:
                if len(part) > 0:
                    part_id = id_regex.search(part)
                    if part_id:
                        extras = {'id':"section-" + part_id.group(1)}
                    else:
                        extras = {}
                    body.append(self._tag("div", part, additional_args=extras))
                
            if len(page_content_parts) > 0:
                temp_body = page_content_parts
            
        for part in temp_body:
            if len(part) > 0:
                part_id = id_regex.search(part)
                if part_id:
                    extras = {'id':"section-" + part_id.group(1)}
                else:
                    extras = {}
                body.append(self._tag("div", part, additional_args=extras))
                    
        body = "\n".join(body)
        
        if insert_head:
            head = self._get_head(json_data)
            return head + self._tag("body", body)
        else:
            return body