console.log(`Uploads: ${uploads}`);
if (uploads) {
    // each key is the hash and value is the filename
    // Get the keys and hashes
    const keys = Object.keys(uploads);
    for (let i = 0; i < keys.length; i++) {
        const hash = keys[i];
        const filename = uploads[hash];
        console.log(`${hash} - ${filename}`);
        const link = document.createElement("a");
        link.href = `/${hash}`;
        link.innerText = filename;
        uploads_list.appendChild(link);
        uploads_list.appendChild(document.createElement("br"));
    }
}