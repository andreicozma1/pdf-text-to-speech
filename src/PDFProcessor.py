import argparse
import os
import re
import string
from tqdm import tqdm
import fitz


class PDFProcessor:

    def __init__(self, pdf_file_path):
        self.input_file_path = pdf_file_path
        output_file_path_base = os.path.join(os.path.dirname(self.input_file_path),
                                             os.path.basename(self.input_file_path).split('.')[0])
        self.output_file_path_txt_original = f"{output_file_path_base}_original.txt"
        self.output_file_path_txt_processed = f"{output_file_path_base}_processed.txt"
        ########################################################################
        # PDF Processing Configuration
        ########################################################################
        # Remove parentheses/brackets/braces and contents in between from processed text
        self.skip_parentheses = True
        self.skip_brackets = True
        self.skip_braces = True
        # For any of the above only remove if there are only digits inside
        # (Useful for removing in-text references/citations in research papers)
        self.skip_only_if_digits_inside = True

        ########################################################################
        # Remove line while processing text depending on the ratio of ascii to non-ascii characters
        # (Useful for removing remnants of weirdly encoded PDF tables and charts, etc)
        self.remove_majority_non_ascii_lines = True
        self.remove_majority_non_ascii_ratio = 0.85
        # Remove lines that contain only symbols and digits
        self.remove_symbols_and_digits_only_lines = True
        # Remove lines that contain only symbols, digits, or URLs
        self.remove_symbols_only_lines = True
        self.remove_digits_only_lines = True
        self.remove_urls_only_lines = True
        ########################################################################

        self.removals = {'remove_majority_non_ascii_lines': [],
                         'symbols_and_digits_only_lines': [],
                         'symbols_only_lines': [],
                         'digits_only_lines': [],
                         'urls_only_lines': []}

    def filter(self, text):
        # text = text.strip()
        ntxt = re.sub(r"\s+", "", text)

        re_pattern = "[^a-zA]+" if self.skip_only_if_digits_inside else ".*?"

        if self.skip_parentheses:
            text = re.sub(f"\({re_pattern}\)", "", text)
        if self.skip_brackets:
            text = re.sub(f"\[{re_pattern}\]", "", text)
        if self.skip_braces:
            text = re.sub(f"\{{{re_pattern}\}}", "", text)

        if self.remove_symbols_and_digits_only_lines and all((i in string.punctuation or i.isdigit()) for i in ntxt):
            self.removals['symbols_and_digits_only_lines'].append(text)
            return None

        if self.remove_symbols_only_lines and all(i in string.punctuation for i in ntxt):
            self.removals['symbols_only_lines'].append(text)
            return None

        if self.remove_digits_only_lines and all(i.isdigit() for i in ntxt):
            self.removals['digits_only_lines'].append(text)
            return None

        if self.remove_majority_non_ascii_lines:
            # Get the number of non-ascii characters in the ntxt string
            num_ascii = len(ntxt.encode("ascii", "ignore"))
            num_total = len(ntxt)
            if num_ascii / num_total < self.remove_majority_non_ascii_ratio:
                self.removals['remove_majority_non_ascii_lines'].append(text)
                return None

        if self.remove_urls_only_lines:
            # remove all digits, symbols, and whitespace
            ntxt = re.sub("[^a-zA-Z]", "", text)
            if (ntxt.startswith("http") or
                    ntxt.startswith("www")):
                self.removals['urls_only_lines'].append(text)
                return None

        return text

    def process(self):
        text_list = []
        doc = fitz.Document(self.input_file_path)

        page: fitz.Page
        with open(self.output_file_path_txt_original, "w") as f:
            for page in tqdm(doc):
                label = page.get_label()
                label = f' ({label})' if label != '' else ''
                buf_page_num = f"\n<CENTER><UNDERLINE><BOLD>PAGE #{page.number + 1}{label}<BOLD><UNDERLINE><CENTER>\n\n"
                text_list.append(buf_page_num)
                page = page.get_textpage()
                blocks = page.extractBLOCKS()

                for b in blocks:
                    txt = b[4]
                    # txt = txt.strip()
                    txt = txt.replace("\n ", "\n")
                    f.write(txt)
                    f.write("-" * 80 + "\n")

                    sections = txt.split("\n\n")
                    paragraphs = []
                    for s in sections:
                        #################
                        # MODE 1
                        #################
                        txt_split = s.split("\n")
                        paragraphs.append(" ".join(txt_split))

                    for p in paragraphs:
                        txt = self.filter(p)
                        if txt is not None:
                            txt = txt + "\n\n"
                            txt = txt.replace("  ", " ")
                            txt = txt.replace("- ", "-")
                            txt = txt.replace(" -", "-")
                            txt = txt.replace(" , ", ", ")
                            txt = txt.replace(" .", ".")
                            text_list.append(txt)

        with open(self.output_file_path_txt_processed, "w") as f:
            for item in text_list:
                f.write(item)
            # f.write(text)

    def clean(self):
        if os.path.exists(self.output_file_path_txt_processed):
            os.remove(self.output_file_path_txt_processed)
        if os.path.exists(self.output_file_path_txt_original):
            os.remove(self.output_file_path_txt_original)


if __name__ == '__main__':
    # Get arguments with -i being required and -o being optional
    # Use argparse to parse the arguments
    args = argparse.ArgumentParser(description='Process PDF files')
    args.add_argument('-i', '--input', help='Input file', required=True)
    args.add_argument('-o', '--output', help='Output file', required=False)
    args.add_argument('-d', '--debug', help='Debug mode', required=False, action='store_true')

    # Parse the arguments
    args = args.parse_args()

    pp = PDFProcessor(args.input)
    text = pp.extract_text()
    print(text)
