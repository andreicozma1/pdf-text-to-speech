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
        self.output_filepath_txt = f"{output_filepath}.txt"
        self.output_filepath_pkl = f"{output_filepath}.pkl"
        self.output_filepath_json = f"{output_filepath}.json"

        self.speaking_rate = 1
        self.pitch = 0.0
        self.language_code = "en-US"

        # Validation of configuration options
        if self.speaking_rate < 0.25 or self.speaking_rate > 4.0:
            raise Exception("Invalid speaking rate, must be between 0.25 and 4.0")

        if self.pitch < -20 or self.pitch > 20:
            raise Exception("Invalid pitch, must be between -20 and 20")

        self.skip_brackets = True
        self.skip_braces = True
        self.skip_parentheses = False

        sampleRate = 24000
        bitsPerSample = 16
        channels = 1
        self.wav_header = self.genWavHeader(
            sampleRate, bitsPerSample, channels)
        # first_run = True

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
        self.filters_folder = "./filters"
        self.filters = {
            'authors': {
                'cutoff': 0.4,
            },
            'references': {
                'cutoff': 0.005,
            },
            'custom': {
                'cutoff': 0.4,
            }
        }
        self.formatting = ["BOLD", "ITALIC",
                           "UNDERLINE", "STRIKETHROUGH", "CENTER"]

        self.doc = None
        self.text_audio_map = self.read_text_audio_map()

    def setup_doc(self, filename):
        # Setting up removals
        self.removals = {'parentheses': [],
                         'brackets': [],
                         'braces': [],
                         'other': []}

        # Setting up filters
        for filter_name in self.filters:
            filter_authors_path = os.path.join(
                self.filters_folder, filter_name)
            self.filters[filter_name]['items'] = []
            if os.path.isfile(filter_authors_path):
                with open(filter_authors_path, "r") as f:
                    lines = [line.strip() for line in f.readlines()]
                    for line in lines:
                        if line != "":
                            self.filters[filter_name]['items'].append(line)
            else:
                # create file
                with open(filter_authors_path, "w") as f:
                    pass
            self.removals[filter_name] = []

        # Setting up document
        return fitz.Document(filename)

    def get_data(self):
        data = self.load_data()
        if self.doc and not self.doc.is_closed:
            data['info'].update({
                'page_count': self.doc.page_count,
                'has_links': self.doc.has_links(),
                'has_annots': self.doc.has_annots(),
                'is_encrypted': self.doc.is_encrypted,
                'is_password_protected': self.doc.needs_pass,

            })
            data.update({
                'toc': self.doc.get_toc(),
            })

        data['info'].update({'file_name': os.path.basename(self.filename),
                             'is_processed': self.is_processed(),
                             'is_open': bool(self.doc and not self.doc.is_closed)})

        data.update({
            'text_list': [i[0] for i in self.text_audio_map] if self.text_audio_map else [],
            'removals': self.removals,
            'last_updated': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        return data

    def save_data(self):
        try:
            with open(self.output_filepath_json, "w") as f:
                json.dump(self.get_data(), f, indent=4)
            return True
        except Exception:
            traceback.print_exc()

        return False

    def load_data(self):
        data = {'info': {}}
        if os.path.isfile(self.output_filepath_json):
            print(f"Data File Exists... Loading: {self.output_filepath_json}")
            try:
                with open(self.output_filepath_json, "r") as f:
                    data = json.load(f)
            except Exception:
                traceback.print_exc()
        else:
            print(f"Data File Does Not Exist... Creating: {self.output_filepath_json}")
        return data

    def filter(self, text):
        if self.skip_parentheses:
            self.removals['parentheses'].append(text)
            text = re.sub("\(.*?\)", "", text)
        if self.skip_brackets:
            self.removals['brackets'].append(text)
            text = re.sub("\[.*?\]", "", text)
        if self.skip_braces:
            self.removals['braces'].append(text)
            text = re.sub("\{.*?\}", "", text)

        sim_author = difflib.get_close_matches(
            text, self.filters['authors']['items'], cutoff=self.filters['authors']['cutoff'])
        sim_ref = difflib.get_close_matches(
            text, self.filters['references']['items'], cutoff=self.filters['references']['cutoff'])
        sim_custom = difflib.get_close_matches(
            text, self.filters['custom']['items'], cutoff=self.filters['custom']['cutoff'])

        shouldAdd = True
        if (len(text.split()) <= 4 and len(sim_author) > 0):
            self.removals['authors'].append(text)
            shouldAdd = False

        if (text.startswith('[') and len(sim_ref) > 0):
            self.removals['references'].append(text)
            shouldAdd = False

        if len(sim_custom) > 0:
            self.removals['custom'].append(text)
            shouldAdd = False

        if "".join(text.split()).isdigit() or \
                text.startswith("http") or \
                text.startswith("www") or \
                len(text) == 0:
            self.removals['other'].append(text)
            shouldAdd = False

        if not shouldAdd:
            return None
        return text

    def read_text_audio_map(self):
        if os.path.isfile(self.output_filepath_pkl):
            with open(self.output_filepath_pkl, "rb") as f:
                return pickle.load(f)
        else:
            return None

    def save_text_audio_map(self, overwrite=False):
        if overwrite or not os.path.exists(self.output_filepath_pkl):
            with open(self.output_filepath_pkl, "wb") as f:
                pickle.dump(self.text_audio_map, f)
            print(
                f" - Saved text_audio_map (overwrite={overwrite}): `{self.output_filepath_pkl}`")

    def is_processed(self):
        return self.text_audio_map is not None

    def process(self):
        print(f"PROCESSING: {self.output_filename}")

        self.doc = self.setup_doc(self.filename)

        text_buf = []
        page: fitz.Page
        for page in tqdm(self.doc):
            label = page.get_label()
            label = f' ({label})' if label != '' else ''

            buf_page_num = f"\n<CENTER><UNDERLINE><BOLD>PAGE #{page.number + 1}{label}<BOLD><UNDERLINE><CENTER>\n\n"
            # if text_buf and not text_buf[-1].endswith('\n'):
            # buf_page_num =  + buf_page_num
            # if text_buf:
            #     print("=" * 50)
            #     print(text_buf[-1])
            text_buf.append(buf_page_num)
            page = page.get_textpage()
            blocks = page.extractBLOCKS()
            for b in blocks:
                txt = b[4].strip()
                txt = " ".join(txt.split("\n")).strip()
                txt = self.filter(txt)
                if txt is not None:
                    # print("=" * 50)
                    # print(txt)
                    # print(txt_new)

                    # text =
                    text = txt + "\n\n"
                    text = text.replace("  ", " ")
                    text = text.replace("- ", "")
                    text = text.replace(" , ", ", ")
                    text = text.replace(" .", ".")

                    text_buf.append(text)

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
                    # if len(sentences) > 1 and not l.endswith("\n"):

                    if "Roesner et al" in l:
                        print(l)
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
                    print(
                        "WARNING: Loaded text list audio is different length than original text list audio")
                    # remove the old file
                    os.remove(self.output_filepath_txt)
                print(
                    f" - Loaded initial cache from: `{self.output_filepath_txt}`")
                print(
                    f" - Total number of text sequences: {len(self.text_audio_map)}")
                print(
                    f" - Number of pre-loaded audio sequences: {len([x for x in self.text_audio_map if x[1] is not None])}")

        self.save_text_audio_map(overwrite=False)
        self.save_data()
        self.doc.close()
        return self.is_processed()

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
                self.save_text_audio_map(overwrite=True)
            except KeyboardInterrupt as e:
                self.save_text_audio_map(overwrite=True)
                raise KeyboardInterrupt from e

        else:
            print(f"STREAMING [CACHE]: {text.strip()}")

        audio_io = io.BytesIO(audio)
        return audio_io.read()

    def clean(self):
        if os.path.exists(self.output_filepath_txt):
            os.remove(self.output_filepath_txt)
        if os.path.exists(self.output_filepath_pkl):
            os.remove(self.output_filepath_pkl)
        if os.path.exists(self.output_filepath_json):
            os.remove(self.output_filepath_json)

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
