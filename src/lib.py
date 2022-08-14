import difflib
import os
import pickle
import fitz
from google.cloud import texttospeech
from tqdm import tqdm
import re
import simpleaudio as sa
import io
# print("=" * 80)
# print("# PDF Text To Speech")

# # Setting up configuration
# filename = "./pdf-sample.pdf"


class PDF_TTS:

    def __init__(self, filename) -> None:
        self.output_filename = os.path.basename(filename).split('.')[0]
        output_filepath = os.path.join(
            os.path.dirname(filename), self.output_filename)
        self.output_filepath_txt = f"{output_filepath}.txt"
        self.output_filepath_pkl = f"{output_filepath}.pkl"

        self.speaking_rate = 1
        self.pitch = 0.0
        self.language_code = "en-US"

        # Validation of configuration options
        if self.speaking_rate < 0.25 or self.speaking_rate > 4.0:
            raise Exception(
                "Invalid speaking rate, must be between 0.25 and 4.0")

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

        self.doc = self.setup(filename)

        self.text_audio_map = self.read_text_audio_map()

        self.formatting = ["BOLD", "ITALIC", "UNDERLINE", "STRIKETHROUGH"]

    def setup(self, filename):
        # Setting up removals
        self.removals = {'other': [],
                         'parentheses': [],
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
        info = {
            'info': {
                'file_name': os.path.basename(self.doc.name),
                'page_count': self.doc.page_count,
                'has_links': self.doc.has_links(),
                'has_annots': self.doc.has_annots(),
                'is_encrypted': self.doc.is_encrypted,
                'is_password_protected': self.doc.needs_pass,
                'is_processed': self.is_processed(),
            },
            'toc': self.doc.get_toc(),
            'text_list': [i[0] for i in self.text_audio_map] if self.text_audio_map else [],
            'removals': self.removals,
        }
        return info

    def filter(self, text):
        # text = text.replace("\n", " ").strip()
        # text = text.replace("\n", " ").strip()
        text_stripped = text.strip()

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
            text_stripped, self.filters['authors']['items'], cutoff=self.filters['authors']['cutoff'])
        sim_ref = difflib.get_close_matches(
            text_stripped, self.filters['references']['items'], cutoff=self.filters['references']['cutoff'])
        sim_custom = difflib.get_close_matches(
            text_stripped, self.filters['custom']['items'], cutoff=self.filters['custom']['cutoff'])

        shouldAdd = True
        if (len(text_stripped.split()) <= 4 and len(sim_author) > 0):
            self.removals['authors'].append(text_stripped)
            shouldAdd = False

        if (text_stripped.startswith('[') and len(sim_ref) > 0):
            self.removals['references'].append(text_stripped)
            shouldAdd = False

        if len(sim_custom) > 0:
            self.removals['custom'].append(text_stripped)
            shouldAdd = False

        if "".join(text_stripped.split()).isdigit() or \
            text_stripped.startswith("http") or \
            text_stripped.startswith("www") or \
                len(text_stripped) == 0:

            self.removals['other'].append(text_stripped)
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
        print(f"# PROCESSING: {self.output_filename}")

        text_buf = []
        page: fitz.Page
        for page in tqdm(self.doc):
            label = page.get_label()
            label = f' ({label})' if label != '' else ''
            text_buf.append(
                f"<UNDERLINE><BOLD>PAGE #{page.number}{label}<BOLD><UNDERLINE>\n\n")
            page = page.get_textpage()
            blocks = page.extractBLOCKS()
            for b in blocks:
                txt = b[4]
                txt_new = self.filter(txt)
                if txt_new is not None:
                    # print("=" * 50)
                    # print(txt)
                    # print(txt_new)

                    text = " ".join(txt_new.split("\n"))
                    text += "\n\n"
                    text = text.replace("  ", " ")
                    text = text.replace("- ", "")
                    text = text.replace(" , ", ", ")
                    text = text.replace(" .", ".")

                    text_buf.append(text)

        with open(self.output_filepath_txt, "w") as f:
            for i in range(len(text_buf)):
                line = text_buf[i]
                f.write(line)

        self.text_audio_map = []
        with open(self.output_filepath_txt, "r") as f:
            lines = f.readlines()
            for line in lines:
                sentences = line.split(". ")
                for i, l in enumerate(sentences):
                    if len(sentences) > 1 and not l.endswith("\n"):
                        l += ". "
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
        return self.is_processed()

    def stream_one(self, index):
        if not self.is_processed():
            print(" => File not processed yet. Please run `process()` first.")
            return None
        text, audio = self.text_audio_map[index]

        # print(f" - {index}: {text}")
        # is_audio_available = audio is not None
        # print(
        #     f"{'(' if not is_audio_available else '['}{i+1}/{len(self.text_audio_map)}{')' if not is_audio_available else ']'} {text}")
        if audio is None:
            # Remove formatting from text using the formatting array
            text_clean = text
            for f in self.formatting:
                text_clean = text_clean.replace(f"<{f}>", "")
            print(text_clean)
            synthesis_input = texttospeech.SynthesisInput(text=text_clean)
            audio = self.client.synthesize_speech(input=synthesis_input,
                                                  voice=self.voice,
                                                  audio_config=self.audio_config).audio_content
            # Save updated cache to file
            self.text_audio_map[index] = (text, audio)
            try:
                self.save_text_audio_map(overwrite=True)
            except KeyboardInterrupt:
                self.save_text_audio_map(overwrite=True)
                raise KeyboardInterrupt

        audio_io = io.BytesIO(audio)
        data = audio_io.read()
        # play_obj = sa.WaveObject.from_wave_file(io.BytesIO(audio))
        # print(play_obj)
        # play_obj.play()
        # play_obj.wait_done()
        return data

    def clean(self):
        if os.path.exists(self.output_filepath_txt):
            os.remove(self.output_filepath_txt)
        if os.path.exists(self.output_filepath_pkl):
            os.remove(self.output_filepath_pkl)

    def genWavHeader(self, sampleRate, bitsPerSample, channels):
        datasize = 2000*10**6
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
                                                      'little')               # (2byte)
        # (2byte)
        o += (bitsPerSample).to_bytes(2, 'little')
        # (4byte) Data Chunk Marker
        o += bytes("data", 'ascii')
        # (4byte) Data size in bytes
        o += (datasize).to_bytes(4, 'little')
        return o
