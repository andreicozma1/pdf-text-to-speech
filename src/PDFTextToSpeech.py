import json
import os
import traceback
# import simpleaudio as sa

# print("=" * 80)
# print("# PDF Text To Speech")

# # Setting up configuration
# filename = "./pdf-sample.pdf"
from src.PDFProcessor import PDFProcessor
from src.TTS import TextToSpeech


class PDFTextToSpeech:

    def __init__(self, pdf_file_path) -> None:
        self.input_file_path = pdf_file_path
        output_file_path_base = os.path.join(os.path.dirname(self.input_file_path),
                                             os.path.basename(self.input_file_path).split('.')[0])
        self.output_filepath_json = f"{output_file_path_base}.json"

        self.formatting = ["BOLD", "ITALIC",
                           "UNDERLINE", "STRIKETHROUGH", "CENTER"]

        self.pdf_processor = PDFProcessor(self.input_file_path)
        self.tts = TextToSpeech(self.pdf_processor.output_file_path_txt_processed)

    def get_data(self):
        data = self.load_data()

        text_list = self.tts.text_list()
        num_seqs_cached = self.tts.num_seqs_cached()

        data['info'].update({'file_name': os.path.basename(self.input_file_path),
                             'num_seqs': None if text_list is None else len(text_list),
                             'num_seqs_cached': num_seqs_cached,
                             'is_processed': self.tts.text_audio_map is not None})

        data.update({
            'text_list': text_list,
            'removals': self.pdf_processor.removals,
        })

        print(f"DATA: Saving {self.output_filepath_json}")
        with open(self.output_filepath_json, "w") as f:
            json.dump(data, f, indent=4)
        return data

    def load_data(self):
        print(f"DATA: Loading {self.output_filepath_json} "
              f"[Exists={os.path.isfile(self.output_filepath_json)}]")
        data = {'info': {}}
        if os.path.isfile(self.output_filepath_json):
            try:
                with open(self.output_filepath_json, "r") as f:
                    data = json.load(f)
            except Exception:
                traceback.print_exc()
        return data

    def process(self):
        print(f"PROCESSING")
        self.pdf_processor.process()
        self.tts.process()

    def stream_index(self, index):
        def remove_formatting(text):
            for f in self.formatting:
                text = text.replace(f"<{f}>", "")
            return text

        return self.tts.stream_index(index, remove_formatting)

    def clean(self):
        print("CLEAN")
        self.pdf_processor.clean()
        self.tts.clean()

        if os.path.exists(self.output_filepath_json):
            os.remove(self.output_filepath_json)
