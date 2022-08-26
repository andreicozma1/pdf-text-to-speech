import io
import os
import pickle
import sys

from google.cloud import texttospeech


class TextToSpeech:

    def __init__(self, txt_file_path):
        self.input_file_path = txt_file_path
        output_filepath = os.path.join(os.path.dirname(self.input_file_path),
                                       os.path.basename(self.input_file_path).split('.')[0])
        self.output_filepath_seqs = f"{output_filepath}.seqs"
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
        # TTS Audio Configuration
        ########################################################################
        audio_sample_rate = 24000
        audio_bits_per_sample = 16
        audio_channels = 1
        ########################################################################

        self.wav_header = self.genWavHeader(audio_sample_rate, audio_bits_per_sample, audio_channels)

        self.ssml_gender = texttospeech.SsmlVoiceGender.MALE
        self.audio_encoding = texttospeech.AudioEncoding.LINEAR16

        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code=self.language_code, ssml_gender=self.ssml_gender
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=self.audio_encoding, speaking_rate=self.speaking_rate, pitch=self.pitch
        )
        self.text_audio_map = self.load_text_audio_seqs()

    def process(self):
        print(f"PROCESS_FILE: {self.input_file_path}")
        self.text_audio_map = []
        with open(self.input_file_path, "r") as f:
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
        if os.path.exists(self.output_filepath_seqs):
            with open(self.output_filepath_seqs, "rb") as f:
                text_list_audio_loaded = pickle.load(f)
                if len(text_list_audio_loaded) == len(self.text_audio_map):
                    self.text_audio_map = text_list_audio_loaded
                else:
                    print("WARNING: Loaded text list audio is different length "
                          "than original text list audio")
                    os.remove(self.output_filepath_seqs)

        self.save_text_audio_seqs(overwrite=False)

    def stream_index(self, index, callback):
        if self.text_audio_map is None:
            print(" => File not processed yet. Please run `process()` first.")
            return None
        text, audio = self.text_audio_map[index]

        if audio is None:
            # Remove formatting from text using the formatting array
            text_clean = callback(text)

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

    def load_text_audio_seqs(self):
        print("TEXT-AUDIO-SEQS: Loading ...")
        if not self.output_filepath_seqs:
            print("TEXT-AUDIO-SEQS: No cache file found. Please call process_file first.")
            sys.exit(1)
        if os.path.isfile(self.output_filepath_seqs):
            with open(self.output_filepath_seqs, "rb") as f:
                return pickle.load(f)
        return None

    def save_text_audio_seqs(self, overwrite=False):
        print("TEXT-AUDIO-SEQS: Saving ...")
        if not self.output_filepath_seqs:
            print("TEXT-AUDIO-SEQS: No cache file found. Please call process_file first.")
            sys.exit(1)
        if overwrite or not os.path.exists(self.output_filepath_seqs):
            with open(self.output_filepath_seqs, "wb") as f:
                pickle.dump(self.text_audio_map, f)
            print(
                f" - Saved text_audio_map (overwrite={overwrite}): `{self.output_filepath_seqs}`")

    def clean(self):
        if os.path.exists(self.output_filepath_seqs):
            os.remove(self.output_filepath_seqs)

    def text_list(self):
        return [i[0] for i in self.text_audio_map] if self.text_audio_map else None

    def num_seqs_cached(self):
        return len([x for x in self.text_audio_map if x[1] is not None]) if self.text_audio_map else None

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
        o += (channels * bitsPerSample // 8).to_bytes(2, 'little')  # (2byte)
        # (2byte)
        o += (bitsPerSample).to_bytes(2, 'little')
        # (4byte) Data Chunk Marker
        o += bytes("data", 'ascii')
        # (4byte) Data size in bytes
        o += (datasize).to_bytes(4, 'little')
        return o
