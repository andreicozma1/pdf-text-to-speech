# Play PDF as Audio


## Linux Dependencies:
```
sudo apt-get install -y python3-dev libasound2-dev
```

## Setting up Google TTS:

Follow the instructions here: https://cloud.google.com/text-to-speech/docs/before-you-begin
NOTE: Must have `GOOGLE_APPLICATION_CREDENTIALS` variable set in your environment.

## Running the Web Server:

```
flask run
```

## Usage:

- Go to: http://localhost:5000/
- Upload a PDF file (ex: `pdf-sample.pdf` in the root of this repository)
- Process the file by clicking the `Process` button
- Use the `Prev` and `Next` buttons to navigate through the sentences
- Press `Play` or the `SPACE` button to listen to the audio, automatically progressing to the next sentence
- You can also click on any sentence to navigate to it
  
## Text Filters (WIP):

Filters are used to remove certain patterns of text while processing the PDF file, using `difflib` to compute the similarity ratio between the text and the filter.
Currently there are 3 filters in the following locations:
- Authors: `./filters/authors`
- References: `./filters/references`
- Custom: `./filters/custom`

Note: Each line in these files is it's own filter.
