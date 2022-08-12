// ============================================================
// Main Controls
let btn_process = document.getElementById("btn_process");
let btn_clean = document.getElementById("btn_clean");

let btn_download_txt = document.getElementById("btn_download_txt");
btn_download_txt.hidden = data.is_processed === false;

// ============================================================
// PlayBack Controls
let controls_box = document.getElementById("controlsBox");
controls_box.hidden = data.is_processed === false;

let btn_play = document.getElementById("btn_play");

// ============================================================
// Progress Indicators
let progress_text = document.getElementById("progressText")
let progress_range = document.getElementById("progressRange")
let current_text = document.getElementById("currentText")

// ============================================================
// Full Text Display
let textbox = document.getElementById("textbox");

// ============================================================
// Handle disabling and hiding of certain elements
btn_process.disabled = data.is_processed === true;
btn_clean.disabled = data.is_processed === false;

// ============================================================
// Audio Player
let audio_index = 0

let audio_source = document.getElementById("audio_source");
audio_source.hidden = data.is_processed === false
audio_source.removeEventListener("loadeddata", () => { });

if (data.is_processed === true) {
    audio_source.src = get_stream_url(audio_index);
}

// ============================================================
// ============================================================

function process() {
    console.log("Processing...");
    const parser = new URL(window.location);
    parser.searchParams.set("action", "process");
    window.location = parser.href;
}
function clean() {
    console.log("Cleaning...");
    const parser = new URL(window.location);
    parser.searchParams.set("action", "clean");
    window.location = parser.href;
}

// ============================================================
// ============================================================

function download_pdf() {
    console.log("Downloading PDF...");
    const parser = new URL(window.location);
    parser.searchParams.set("action", "download_pdf");
    window.location = parser.href;
}
function download_txt() {
    console.log("Downloading TXT...");
    const parser = new URL(window.location);
    parser.searchParams.set("action", "download_txt");
    window.location = parser.href;
}

// ============================================================
// ============================================================

function get_stream_url(index) {
    const parser = new URL(window.location);
    parser.searchParams.set("action", "stream");
    parser.searchParams.set("index", index);
    console.log(`Streaming: ${parser.href}`);
    return parser.href;
}



function setProgress() {
    const text = data.text_list[audio_index]

    console.log(`Setting progress: [${audio_index}] - ${text}`);

    progress_text.innerText = `${audio_index}/${data.text_list.length - 1}`
    progress_range.value = audio_index
    current_text.innerText = text
    let active_text = document.getElementById("text_" + audio_index)
    // add class to active text
    active_text.classList.add("active")
}

function load_current_index(play) {
    setProgress();
    audio_source.src = get_stream_url(audio_index)
    audio_source.load();
}

function seek_to_index(index, forward) {
    if (forward === undefined) {
        forward = true;
    }

    index = parseInt(index);

    if (index < 0) {
        index = data.text_list.length - 1;
    }

    if (index > data.text_list.length - 1) {
        index = 0
    }

    console.log(`Attempting to seek to: ${index}`);
    const text = data.text_list[index]
    // strip out whitespace and newlines
    const text_stripped = text.replace(/\s/g, "").replace(/\n/g, "")
    // if there is no text, play the next audio
    if (text_stripped.length === 0) {
        if (forward) {
            seek_to_index(index + 1, forward);
        } else {
            seek_to_index(index - 1, forward);
        }
        return;
    }

    let curr_active = document.getElementById("text_" + audio_index)
    // remove class from active text
    curr_active.classList.remove("active")
    audio_index = index
    console.log("Seeking to: " + audio_index);
    let autoplay = !audio_source.paused
    load_current_index();
    if (autoplay) {
        audio_source.play();
    }
}

// ============================================================
// ============================================================

function toggle_play() {
    if (audio_source.paused) {
        console.log("Playing...");
        load_current_index();
        audio_source.play();
        btn_play.innerText = "Pause";
    } else {
        console.log("Pausing...");
        audio_source.pause();
        btn_play.innerText = "Play";
    }
}

function next() {
    seek_to_index(audio_index + 1, true);
}

function prev() {
    seek_to_index(audio_index - 1, false);
}

document.body.onkeyup = function (e) {
    if (e.key == " " ||
        e.code == "Space" ||
        e.keyCode == 32
    ) {
        toggle_play()
    }
    if (e.key == "ArrowRight" ||
        e.code == "ArrowRight" ||
        e.keyCode == 39
    ) {
        next()
    }
    if (e.key == "ArrowLeft" ||
        e.code == "ArrowLeft" ||
        e.keyCode == 37
    ) {
        prev()
    }
}

audio_source.addEventListener('ended', function (ev) {
    next();
    audio_source.play();
});

// ============================================================
// ============================================================

if (data.text_list.length > 0) {
    progress_range.max = data.text_list.length - 1;
    // Append link elements to the textbox
    for (let i = 0; i < data.text_list.length; i++) {
        const text = data.text_list[i];
        const link = document.createElement("a");
        // set padding to prevent text from overlapping
        link.onclick = function () {
            seek_to_index(i);
        };
        link.id = "text_" + i;
        link.innerText = text;
        textbox.appendChild(link);
        // textbox.appendChild(document.createElement("br"));
    }
    setProgress();
}