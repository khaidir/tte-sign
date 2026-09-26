import id from "./i18n/id.js";

const app = document.querySelector("#app");

function renderPlaceholder(section) {
    const el = document.createElement("p");
    el.textContent = id[section] || id["editor.placeholder"];
    return el;
}

// Upload section logic
const fileInput = document.getElementById("file-input");
const uploadZone = document.getElementById("upload-zone");

if (fileInput && uploadZone) {
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            console.log("File selected:", e.target.files[0].name);
        }
    });

    uploadZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadZone.classList.add("drag-over");
    });

    uploadZone.addEventListener("dragleave", () => {
        uploadZone.classList.remove("drag-over");
    });

    uploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length > 0) {
            console.log("File dropped:", e.dataTransfer.files[0].name);
        }
    });
}

console.log("TTE PDF — Editor loaded");
