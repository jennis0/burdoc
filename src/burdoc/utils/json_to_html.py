"""Convert JSON output into HTML"""

from typing import Any, Dict, List, Optional, Sequence


class JsonHtmlConverter():

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

    def __init__(self):
        self.images: Optional[Dict[str, Sequence[str]]] = None
        self.current_page = 0

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

    def _table_to_html(self, table: Dict[str, Any]) -> str:
        """Turns table into HTML table

        Args:
            table (Dict[str, Any])

        Returns:
            str: HTML
        """
        text = "<table>"

        # For now, only consider first column header. More complex table parsing to come!
        skip_rows = set()
        if 'col_header_index' in table and len(table['col_header_index']) > 0 and table['col_header_index'][0] == 0:
            header = "<theader>"
            if len(table['cells']) > 0:
                header += "".join(
                    [f"<th>{self._cell_to_html(cell)}</th>" for cell in table['cells'][0]])
            header += "</theader>"
            text += header
            skip_rows.add(0)

        for i, row in enumerate(table['cells']):
            if i in skip_rows:
                continue
            cell_text = "".join(
                [f"<td>{self._cell_to_html(cell)}</td>" for cell in row])
            text += f"<tr>{cell_text}</tr>"
        text += "</tbody></table>"

        return text

    def _aside_to_html(self, aside: Dict[str, Any]) -> str:
        """Turns asides into grey-background boxes

        Args:
            aside (Dict[str, Any])

        Returns:
            str: HTML
        """
        item_text = "".join(self._item_to_html(i) for i in aside['items'])
        return f"<div style='background-color:#e0e0e0; padding:10pt; margin:5pt; width:max-content'>{item_text}</div>"

    def _textlist_item_to_html(self, textlist_item: Dict[str, Any], style_type: str) -> str:
        """Turns textlist item into <li>

        Args:
            textlist_item (Dict[str, Any]): textlist_item
            style_type (str): sets 'list-style-type'

        Returns:
            str: HTML
        """
        item_text = ''.join(
            f'<p>{self._text_to_html(e)}</p>' for e in textlist_item['items'])
        return f"<li style=\"list-style-type:{style_type}\">{item_text}</li>"

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
        return f"<{list_type}>{item_text}</{list_type}>"

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
            if span['font']['sc']:
                span_text = span_text.upper()
            if span['font']['bd']:
                span_text = f"<b>{span_text}</b>"
            if span['font']['it']:
                span_text = f"<i>{span_text}</i>"
        
            line_text += f"<span style=\"{style}\">{span_text}</span>"

        return line_text

    def _make_anchor_name(self, text: str) -> str:
        """Creates a consistent anchor name from a piece of text by replacing spaces with 
        '-' and limiting to 12 characters.

        Args:
            text (str): Source text

        Returns:
            str: Anchor name
        """
        return text.replace(" ", "-")[:12]

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
            try:
                id_text = f" id=\"{self.current_page}-{self._make_anchor_name(text['block_text'])}\""
            except:
                id_text = ""
        else:
            id_text = ""

        html_text = f"<{text_type}{id_text}>" + "</br>".join(self._line_to_html(line)
                                                             for line in text['items']) + f"</{text_type}>"
        return html_text

    def _image_to_html(self, image: Dict[str, Any]) -> str:
        
        if not self.images:
            return "<div><h2>MISSING IMAGE</h2></div>"
        
        if image['image'] < len(self.images[self.current_page]):
            image_data = self.images[self.current_page][image['image']]
            return f'<img src="data:image/webp;base64, {image_data}" style="max-width:45%; max-height:300pt">'
        else:
            return f"<div><h2>MISSING IMAGE {image['image']}</h2></div>"

    def _item_to_html(self, item: Dict[str, Any]) -> str:
        """Routes an item to the correct HTML generator based on 'name' attribute

        Args:
            item (Dict[str, Any])

        Returns:
            str: Dict[str, Any]
        """

        if item['name'] in self.route_dict:
            return self.route_dict[item['name']](item)

        raise RuntimeError(
            f"Couldn't find HTML parser for item type \'{item['name']}\'")



    def _get_head(self, json_data):
        text = "<head>"
        text += f"<title>{json_data['metadata']['title']}</title>"
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
        text += "</style>"
        text += "</head>"
        return text

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
        
        if insert_head:
            full_content = self._get_head(json_data) + "<body>"
        else:
            full_content = ""
        
        if 'images' in json_data:
            self.images = json_data['images']
        self.current_page = page_number
        content = "".join(self._item_to_html(i) for i in json_data['content'][page_number])
        
        if insert_page_tags:
            full_content += f"<div><h1 id='anchor-page-{page_number}'>Page {page_number}</h1><hr><div style='max-width:1000px'>{content}</div></div>"
        else:
            full_content += f"<div id='anchor-page-{page_number}'><div style='max-width:600px'>{content}</div></div>"
            
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

        if insert_head:
            full_content = self._get_head(json_data) + "<body>"
        else:
            full_content = ""

        for page_number in json_data['content']:
            full_content += self.convert_page(json_data, page_number, insert_page_tags, False)
            full_content += "<hr>"
        full_content += "</div>"

        if insert_head:
            full_content += "</body>"

        return full_content
