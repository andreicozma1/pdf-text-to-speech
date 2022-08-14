# PDF Text-To-Speech

## Installing Dependencies:
```bash
pip3 install -r requirements.txt
```

## Setting up Google TTS:

Follow the instructions here: https://cloud.google.com/text-to-speech/docs/before-you-begin   

NOTE: You must have `GOOGLE_APPLICATION_CREDENTIALS` variable set in your environment for `Google TTS` to work.

For example, add the credentials file to your `~/.bashrc` or `~/.zshrc` file as follows:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/API_KEYS/XXXXX-XXXXX-XXAYYBZZCABC.json"
```

Then re-source your `~/.bashrc` (or `~/.zshrc`) file as such:

```bash
source ~/.bashrc # or ~/.zshrc
```

## Running the Web Server:

```
flask run
```

## Usage:

- Once the web server is started, navigate to `http://localhost:5000/`.
- Upload a PDF file (ex: `pdf-sample.pdf` in the root of this repository)
- Process the file by clicking the `Process` button
- Press `Prev` (or `Left Arrow` button) or `Next` (or `Right Arrow` button) to navigate through the sentences
- Press `Play` or the `Ctrl + SPACE` button to listen to the audio, automatically progressing to the next sentence
- You can also click on any sentence to navigate to it
  
## Interface:

![img.png](img.png)

## Text Filters (WIP):

Filters are used to remove certain patterns of text while processing the PDF file, using `difflib` to compute the similarity ratio between the text and the filter.  
Currently there are 3 filters in the following locations:
- Authors: `./filters/authors`
- References: `./filters/references`
- Custom: `./filters/custom`

Note: Each line in these files is its own filter.
