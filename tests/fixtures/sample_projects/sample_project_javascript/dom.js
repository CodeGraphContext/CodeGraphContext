// Basic DOM manipulation (run in browser)

document.body.style.backgroundColor = "lightblue";

const heading = document.createElement("h1");
heading.textContent = "Hello from JavaScript!";
document.body.appendChild(heading);