import id from "./i18n/id.js";

const fileInput = document.getElementById("verify-file-input");
const uploadZone = document.getElementById("verify-upload-zone");
const resultContainer = document.getElementById("verify-result");

if (fileInput && uploadZone) {
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            console.log("Verify file selected:", e.target.files[0].name);
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
            console.log("Verify file dropped:", e.dataTransfer.files[0].name);
        }
    });
}

if (resultContainer) {
    resultContainer.textContent = id["verify.result.placeholder"];
}

console.log("TTE PDF — Verify page loaded");
