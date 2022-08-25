import datetime
import difflib
import json
import os
import pickle
import traceback
import fitz
from google.cloud import texttospeech
from tqdm import tqdm
import re
# import simpleaudio as sa
import io
import string


# print("=" * 80)
# print("# PDF Text To Speech")

# # Setting up configuration
# filename = "./pdf-sample.pdf"


class PDF_TTS:

    def __init__(self, filename) -> None:
        self.filename = filename
        self.output_filename = os.path.basename(filename).split('.')[0]
        output_filepath = os.path.join(
            os.path.dirname(filename), self.output_filename)
        self.output_filepath_txt_orig = f"{output_filepath}.txt"
        self.output_filepath_txt = f"{output_filepath}_processed.txt"
        self.output_filepath_pkl = f"{output_filepath}.pkl"
        self.output_filepath_json = f"{output_filepath}.json"

        ########################################################################
        # Google TTS Configuration
        ########################################################################
        # Change the speaking rate for Google TTS (Default: 1)
        # (This usually does not need to be changed as it is controlled afterwards through the Web interface)
        self.speaking_rate = 1
        # Change pitch of Google TTS Audio (Default: 0.0)
        self.pitch = 0.0
        # Change language code for Google TTS (Default: en-US)
        self.language_code = "en-US"
        ########################################################################

        ########################################################################
        # Validation of configuration options
        ########################################################################
        if self.speaking_rate < 0.25 or self.speaking_rate > 4.0:
            raise Exception(
                "Invalid speaking rate, must be between 0.25 and 4.0")

        if self.pitch < -20 or self.pitch > 20:
            raise Exception("Invalid pitch, must be between -20 and 20")
        ########################################################################

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

        ########################################################################
        # TTS Audio Configuration
        sampleRate = 24000
        bitsPerSample = 16
        channels = 1
        ########################################################################
        
        self.wav_header = self.genWavHeader(
            sampleRate, bitsPerSample, channels)

        self.ssml_gender = texttospeech.SsmlVoiceGender.MALE
        self.audio_encoding = texttospeech.AudioEncoding.LINEAR16

        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code=self.language_code, ssml_gender=self.ssml_gender
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=self.audio_encoding, speaking_rate=self.speaking_rate, pitch=self.pitch
        )

        self.removals = None
        self.formatting = ["BOLD", "ITALIC",
                           "UNDERLINE", "STRIKETHROUGH", "CENTER"]

        self.doc = None
        self.text_audio_map = self.load_text_audio_seqs()

    def setup_doc(self, filename):
        # Setting up removals

        self.removals = {'remove_majority_non_ascii_lines': [],
                         'symbols_and_digits_only_lines': [],
                         'symbols_only_lines': [],
                         'digits_only_lines': [],
                         'urls_only_lines': []}

        # Setting up document
        return fitz.Document(filename)

    def get_data(self):
        if not os.path.isfile(self.output_filepath_json):
            self.write_data()
        with open(self.output_filepath_json, "r") as f:
            data = json.load(f)
        return data

    def write_data(self):
        data = self.load_data()
        if self.doc and not self.doc.is_closed:
            data['info'].update({
                'page_count': self.doc.page_count,
                'has_links': self.doc.has_links(),
                'has_annots': self.doc.has_annots(),
                'is_encrypted': self.doc.is_encrypted,
                'is_password_protected': self.doc.needs_pass,
                'last_processed': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            data.update({
                'toc': self.doc.get_toc(),
            })

        data['info'].update({'file_name': os.path.basename(self.filename),
                             'is_processed': self.is_processed(),
                             'num_seqs': len(self.text_audio_map) if self.text_audio_map else 0,
                             'num_seqs_cached': len(
                                 [x for x in self.text_audio_map if x[1] is not None]) if self.text_audio_map else 0,
                             'is_open': bool(self.doc and not self.doc.is_closed)})

        data.update({
            'text_list': [i[0] for i in self.text_audio_map] if self.text_audio_map else [],
            'removals': self.removals,
        })

        print(f"DATA: Saving {self.output_filepath_json}")
        with open(self.output_filepath_json, "w") as f:
            json.dump(data, f, indent=4)
        return data

    def load_data(self):
        print(
            f"DATA: Loading {self.output_filepath_json} [Exists={os.path.isfile(self.output_filepath_json)}]")
        data = {'info': {}}
        if os.path.isfile(self.output_filepath_json):
            try:
                with open(self.output_filepath_json, "r") as f:
                    data = json.load(f)
            except Exception:
                traceback.print_exc()
        return data

    def filter(self, text):
        # text = text.strip()
        text_stripped = text.strip()
        ntxt = re.sub(r"\s+", "", text)

        if not self.skip_only_if_digits_inside:
            re_pattern = ".*?"
        else:
            # match digits, special characters, and spaces
            re_pattern = "[^a-zA]+"

        if self.skip_parentheses:
            text = re.sub(f"\({re_pattern}\)", "", text)
        if self.skip_brackets:
            text = re.sub(f"\[{re_pattern}\]", "", text)
        if self.skip_braces:
            text = re.sub(f"\{{{re_pattern}\}}", "", text)

        # if self.remove_symbols_only_lines and all(i in string.punctuation for i in text.replace(" ", "")):
        #     self.removals['symbols_only_lines'].append(text)
        #     return None

        # if self.remove_digits_only_lines and all(i.isdigit() for i in text.replace(" ", "")):
        #     self.removals['digits_only_lines'].append(text)
        #     return None

        if self.remove_symbols_and_digits_only_lines:
            if all((i in string.punctuation or i.isdigit()) for i in ntxt):
                self.removals['symbols_and_digits_only_lines'].append(text)
                return None

        if self.remove_symbols_only_lines:
            if all(i in string.punctuation for i in ntxt):
                self.removals['symbols_only_lines'].append(text)
                return None

        if self.remove_digits_only_lines:
            if all(i.isdigit() for i in ntxt):
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
        print(f"PROCESSING: {self.output_filename}")

        self.doc = self.setup_doc(self.filename)

        text_buf = []
        page: fitz.Page
        with open(self.output_filepath_txt_orig, "w") as f:
            for page in tqdm(self.doc):
                label = page.get_label()
                label = f' ({label})' if label != '' else ''
                buf_page_num = f"\n<CENTER><UNDERLINE><BOLD>PAGE #{page.number + 1}{label}<BOLD><UNDERLINE><CENTER>\n\n"

                text_buf.append(buf_page_num)
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
                        
                        #################
                        # MODE 2
                        #################
                        # print(txt_split)
                        # minimum = None
                        # start = 0
                        # for i in range(len(txt_split)):
                        #     p = txt_split[i]
                        #     if minimum is None:
                        #         minimum = len(p)
                        #     print(f"\t {p} ({minimum})")
                        #     if i >= len(txt_split) - 1 or (p.endswith('.') and (len(txt_split[i+1]) != 0 and txt_split[i + 1][0].isupper()) and len(p) < minimum):
                        #         paragraphs.append(" ".join(txt_split[start : i + 1]))                           
                        #         start = i + 1
                        #         minimum = None
                        #         print("\t Appended")
                        #         continue
                                
                        #     minimum = (minimum + len(p)) / 2
                        # print(f"\t {start}")
                        
                    for p in paragraphs:
                        txt = self.filter(p)
                        if txt is not None:
                            txt = txt + "\n\n"
                            txt = txt.replace("  ", " ")
                            txt = txt.replace("- ", "-")
                            txt = txt.replace(" -", "-")
                            txt = txt.replace(" , ", ", ")
                            txt = txt.replace(" .", ".")
                            text_buf.append(txt)

        with open(self.output_filepath_txt, "w") as f:
            for item in text_buf:
                f.write(item)

        self.text_audio_map = []
        with open(self.output_filepath_txt, "r") as f:
            lines = f.readlines()
            for line in lines:
                sentences = line.strip().split(". ")
                for i, l in enumerate(sentences):
                    if l == "":
                        continue
                    if l.endswith("\n"):
                        l += "\n"
                    elif i < len(sentences) - 1:
                        l += ". "
                    else:
                        l += "\n"
                    self.text_audio_map.append((l, None))

        # Save initial text to file, with no audio
        if os.path.exists(self.output_filepath_pkl):
            with open(self.output_filepath_pkl, "rb") as f:
                text_list_audio_loaded = pickle.load(f)
                if len(text_list_audio_loaded) == len(self.text_audio_map):
                    self.text_audio_map = text_list_audio_loaded
                else:
                    # remove the old file
                    print("WARNING: Loaded text list audio is different length "
                          "than original text list audio")
                    os.remove(self.output_filepath_txt)

        self.save_text_audio_seqs(overwrite=False)
        self.write_data()
        self.doc.close()

    def stream_one(self, index):
        if not self.is_processed():
            print(" => File not processed yet. Please run `process()` first.")
            return None
        text, audio = self.text_audio_map[index]

        if audio is None:
            # Remove formatting from text using the formatting array
            text_clean = text
            for f in self.formatting:
                text_clean = text_clean.replace(f"<{f}>", "")
            print(f"STREAMING [API]: {text.strip()}")
            synthesis_input = texttospeech.SynthesisInput(text=text_clean)
            audio = self.client.synthesize_speech(input=synthesis_input,
                                                  voice=self.voice,
                                                  audio_config=self.audio_config).audio_content
            # Save updated cache to file
            self.text_audio_map[index] = (text, audio)
            try:
                self.save_text_audio_seqs(overwrite=True)
            except KeyboardInterrupt as e:
                self.save_text_audio_seqs(overwrite=True)
                raise KeyboardInterrupt from e

        else:
            print(f"STREAMING [CACHE]: {text.strip()}")

        audio_io = io.BytesIO(audio)
        return audio_io.read()

    def genWavHeader(self, sampleRate, bitsPerSample, channels):
        datasize = 2000 * 10 ** 6
        # (4byte) Marks file as RIFF
        o = bytes("RIFF", 'ascii')
        # (4byte) File size in bytes excluding this and RIFF marker
        o += (datasize + 36).to_bytes(4, 'little')
        # (4byte) File type
        o += bytes("WAVE", 'ascii')
        # (4byte) Format Chunk Marker
        o += bytes("fmt ", 'ascii')
        # (4byte) Length of above format data
        o += (16).to_bytes(4, 'little')
        # (2byte) Format type (1 - PCM)
        o += (1).to_bytes(2, 'little')
        # (2byte)
        o += (channels).to_bytes(2, 'little')
        # (4byte)
        o += (sampleRate).to_bytes(4, 'little')
        o += (sampleRate * channels * bitsPerSample //
              8).to_bytes(4, 'little')  # (4byte)
        o += (channels * bitsPerSample // 8).to_bytes(2,
                                                      'little')  # (2byte)
        # (2byte)
        o += (bitsPerSample).to_bytes(2, 'little')
        # (4byte) Data Chunk Marker
        o += bytes("data", 'ascii')
        # (4byte) Data size in bytes
        o += (datasize).to_bytes(4, 'little')
        return o

    def is_processed(self):
        return self.text_audio_map is not None

    def load_text_audio_seqs(self):
        print("TEXT-AUDIO-SEQS: Loading ...")

        if os.path.isfile(self.output_filepath_pkl):
            with open(self.output_filepath_pkl, "rb") as f:
                return pickle.load(f)
        else:
            return None

    def save_text_audio_seqs(self, overwrite=False):
        print("TEXT-AUDIO-SEQS: Saving ...")
        if overwrite or not os.path.exists(self.output_filepath_pkl):
            with open(self.output_filepath_pkl, "wb") as f:
                pickle.dump(self.text_audio_map, f)
            print(
                f" - Saved text_audio_map (overwrite={overwrite}): `{self.output_filepath_pkl}`")

    def clean(self):
        if os.path.exists(self.output_filepath_txt):
            os.remove(self.output_filepath_txt)
        if os.path.exists(self.output_filepath_txt_orig):
            os.remove(self.output_filepath_txt_orig)
        if os.path.exists(self.output_filepath_pkl):
            os.remove(self.output_filepath_pkl)
        if os.path.exists(self.output_filepath_json):
            os.remove(self.output_filepath_json)
