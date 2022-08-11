import difflib
import io
import os
import pickle
import sys
import fitz
from google.cloud import texttospeech
import simpleaudio as sa
from tqdm import tqdm
import re

print("=" * 80)
print("# PDF Text To Speech")

# Setting up configuration
filename = "./pdf-sample.pdf"

start_sequence = 0
speaking_rate = 1.5
pitch = 0.0
language_code = "en-US"

skip_brackets = True
skip_braces = True
skip_parentheses = False

ssml_gender = texttospeech.SsmlVoiceGender.MALE
audio_encoding = texttospeech.AudioEncoding.LINEAR16

# Setting up filters
filter_authors_path = os.path.join("filters", "authors")
sim_author_ex = []
if os.path.isfile(filter_authors_path):
    with open(filter_authors_path, "r") as f:
        lines = f.readlines()
        for line in [line.strip() for line in lines]:
            sim_author_ex.append(line)
else:
    # create file
    with open(filter_authors_path, "w") as f:
        pass

filter_authors_path = os.path.join("filters", "references")
sim_ref_ex = []
if os.path.isfile(filter_authors_path):
    with open(filter_authors_path, "r") as f:
        lines = f.readlines()
        for line in [line.strip() for line in lines]:
            sim_ref_ex.append(line)
else:
    # create file
    with open(filter_authors_path, "w") as f:
        pass

filter_authors_path = os.path.join("filters", "custom")
sim_custom_ex = []
if os.path.isfile(filter_authors_path):
    with open(filter_authors_path, "r") as f:
        lines = f.readlines()
        for line in [line.strip() for line in lines]:
            sim_custom_ex.append(line)
else:
    # create file
    with open(filter_authors_path, "w") as f:
        pass

# Validation of configuration options
if speaking_rate < 0.25 or speaking_rate > 4.0:
    raise Exception("Invalid speaking rate, must be between 0.25 and 4.0")

if pitch < -20 or pitch > 20:
    raise Exception("Invalid pitch, must be between -20 and 20")

###
output_filename = os.path.basename(filename).split('.')[0]

removals_author = []
removals_ref = []
removals_custom = []
removals_other = []

removals_parentheses = []
removals_brackets = []
removals_braces = []

def filter(text):
    text = text.replace("\n", " ").strip()
    shouldAdd = True

    sim_author = difflib.get_close_matches(text, sim_author_ex, cutoff=0.4)
    sim_ref = difflib.get_close_matches(text, sim_ref_ex, cutoff=0.005)
    sim_custom = difflib.get_close_matches(text, sim_custom_ex, cutoff=0.4)

    if (len(text.split()) <= 4 and len(sim_author) > 0):
        removals_author.append(text)
        shouldAdd = False
        
    if (text.startswith('[') and len(sim_ref) > 0):
        removals_ref.append(text)
        shouldAdd = False
       
    if len(sim_custom) > 0:
        removals_custom.append(text)
        shouldAdd = False
    
    if "".join(text.split()).isdigit() or \
        text.startswith("http") or \
        text.startswith("www") or \
            len(text) == 0:
                
        removals_other.append(text)
        shouldAdd = False                
    return shouldAdd

print()
print("=" * 80)
print("# PROCESSING")

pages_processed = 0
blocks_processed = 0

doc = fitz.open(filename)

print(f"- Filename: {doc.name}")
print(f"- Is Encrypted? {doc.is_encrypted}")
print(f"- Needs Password? {doc.needs_pass}")

text_buf = []
page: fitz.Page
for page in tqdm(doc):
    page = page.get_textpage()
    blocks = page.extractBLOCKS()
    for b in blocks:
        txt = b[4].strip()
        shouldAdd = filter(txt)
        
        if shouldAdd:
            text = " ".join(txt.split("\n"))
            text += "\n\n"
            
            if skip_parentheses:
                removals_parentheses.append(text)
                text = re.sub("\(.*?\)","",text)
            if skip_brackets:
                removals_brackets.append(text)
                text = re.sub("\[.*?\]","",text)
            if skip_braces:
                removals_braces.append(text)
                text = re.sub("\{.*?\}","",text)

            text = text.replace("- ", "")
            text = text.replace(" , ", ", ")
            text_buf.append(text)
        blocks_processed += 1
    pages_processed += 1

print(f" - Pages processed: {pages_processed}")
print(f" - Blocks processed: {blocks_processed}")
print(f" - Author removals: {len(removals_author)}")
print(f" - Reference removals: {len(removals_ref)}")
print(f" - Custom removals: {len(removals_custom)}")
print(f" - Other removals: {len(removals_other)}")
print(f" - Parentheses removals: {len(removals_parentheses)}")
print(f" - Brackets removals: {len(removals_brackets)}")
print(f" - Braces removals: {len(removals_braces)}")

with open("removals_author.txt", "w") as f:
    for item in removals_author:
        f.write(f"{item}\n")
        
with open("removals_ref.txt", "w") as f:
    for item in removals_ref:
        f.write(f"{item}\n")
        
with open("removals_custom.txt", "w") as f:
    for item in removals_custom:
        f.write(f"{item}\n")
        
with open("removals_other.txt", "w") as f:
    for item in removals_other:
        f.write(f"{item}\n")


print()
print("=" * 80)
print("# PRE-CACHING")

with open(f"{output_filename}.txt", "w") as f:
    for i in range(len(text_buf)):
        line = text_buf[i]
        if line == '\n\n':
            f.write(f'\n\n')
        else:
            f.write(line)
            
        
text_list_audio = []
with open(f"{output_filename}.txt", "r") as f:
    lines = f.readlines()
    for line in lines:
        sentences = line.split(". ")
        for i, l in enumerate(sentences):
            l = l.strip()
            if l == "":
                continue
            text_list_audio.append((l, None))
            

# Save initial text to file, with no audio        
filename_pickle = f"{output_filename}.pkl"



if os.path.exists(filename_pickle):
    with open(filename_pickle, "rb") as f:
        text_list_audio_loaded = pickle.load(f)
        if len(text_list_audio_loaded) == len(text_list_audio):
            text_list_audio = text_list_audio_loaded
        else:
            print("WARNING: Loaded text list audio is different length than original text list audio")
            # remove the old file
            os.remove(filename_pickle)
        print(f" - Loaded initial cache from: `{filename_pickle}`")
        print(f" - Total number of text sequences: {len(text_list_audio)}")
        print(f" - Number of pre-loaded audio sequences: {len([x for x in text_list_audio if x[1] is not None])}")

if not os.path.exists(filename_pickle):
    with open(filename_pickle, "wb") as f:
        pickle.dump(text_list_audio, f)
    print(f" - Saved initial cache to: `{filename_pickle}`")
      
print()
print("=" * 80)
print("# PLAYBACK")

client = texttospeech.TextToSpeechClient()
voice = texttospeech.VoiceSelectionParams(
    language_code=language_code, ssml_gender=ssml_gender
)
audio_config = texttospeech.AudioConfig(
    audio_encoding=audio_encoding, speaking_rate=speaking_rate, pitch=pitch
)

if start_sequence >= len(text_list_audio):
    raise Exception(f"Start sequence is greater than total number of text sequences: {start_sequence} > {len(text_list_audio)}")
    
try:
    for i in range(start_sequence, len(text_list_audio)):
        text, audio = text_list_audio[i]
        is_audio_available = audio is not None
        print(f"{'(' if not is_audio_available else '['}{i+1}/{len(text_list_audio)}{')' if not is_audio_available else ']'} {text}")
        if audio is None:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            audio = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config).audio_content
            # Save updated cache to file
            text_list_audio[i] = (text, audio)
            with open(filename_pickle, "wb") as f:
                pickle.dump(text_list_audio, f)
            
        play_obj = sa.WaveObject.from_wave_file(io.BytesIO(audio)).play()
        play_obj.wait_done()
except KeyboardInterrupt:
    print("\n\nKeyboard interrupt detected. Exiting...")
    sys.exit()