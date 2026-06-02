import sys, zipfile, xml.etree.ElementTree as ET

def extract_text(docx_path):
    with zipfile.ZipFile(docx_path) as docx:
        with docx.open('word/document.xml') as xml_file:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            # Namespaces handling
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = []
            for node in root.iterfind('.//w:t', ns):
                texts.append(node.text)
            return '\n'.join(filter(None, texts))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python extract_docx_text.py <path_to_docx>')
        sys.exit(1)
    print(extract_text(sys.argv[1]))
