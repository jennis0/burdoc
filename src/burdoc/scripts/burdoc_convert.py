import argparse
import json
import os

from ..utils.json_html_converter import JsonHtmlConverter

def create_argparser() -> argparse.ArgumentParser:
    """Creates a preconfigured argument parser.

    Returns:
        argparse.ArgumentParser: The argument parser
    """

    argparser = argparse.ArgumentParser()
    
    argparser.add_argument(
        "in_file", type=str,
        help="Path to the pre-extracted JSON file you want to convert",
    )

    argparser.add_argument(
        'out_file', type=str,
        help="Path to file to write output to.\nDefaults to [in-file-stem].html",
        nargs="?"
    )
    
    argparser.add_argument(
        '--format', choices=['html', 'debug-html'],
        help="Format of desired output. Current options are 'html', 'debug-html'",
        default='html', required=False
    )
    
    argparser.add_argument(
        '--tag-classes', type=str,
        help="CSS Classes to be applied to HTML elements. Provide a list of [tag]=\"[class]\".",
        nargs='*', default=""
    )
    
    argparser.add_argument(
        '--css-file', type=str,
        help="Path to a CSS file to be applied to the HTML",
        nargs='?', default=None
    )
    
    argparser.add_argument(
        '--split', choices=['page','h1','h2','h3'],
        help="If page, group output by pages of input document, otherwise group by instance of passed header level",
        nargs='?', default='page'
    )
    
    return argparser

def check_path(path: str):
    '''Checks a given path exists and is a file
    path [str] - Path of file to check
    Raises: FileNotFoundError
    '''
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)


def run():
    """Run the File converter
    """
    
    argparser = create_argparser()
    args = argparser.parse_args()
    
    print(args)
    
    check_path(args.in_file)
    
    with open(args.in_file, encoding='utf-8') as f:
        infile = json.load(f)
        
    split = args.split
    if split == "h3":
       split = ["h1", "h2", "h3"]
    elif split == "h2":
        split = ["h1", "h2"]
    else:
        split = [split]     
        
    if args.css_file:
        check_path(args.css_file)
        with open(args.css_file, encoding="utf-8") as f:
            css = f.read()
    else:
        css = None
        
    classes = {}
    print(args.tag_classes)
    if len(args.tag_classes) > 0:
        for tc in args.tag_classes:
            print(tc)
            parts = tc.split("=")
            if len(parts) != 2:
                raise ValueError("Classes need to be in the format 'tag=\"class1 class2\"")
            classes[parts[0]] = parts[1]
    
    converter = JsonHtmlConverter(split, css=css, classes=classes)
        
    if args.format == "html_debug":
        html_output = converter.convert(infile)
        
    else:
        html_output = converter.convert(infile, insert_page_tags=False)
        
    with open(args.out_file, 'w', encoding='utf-8') as f:
        f.write(html_output)