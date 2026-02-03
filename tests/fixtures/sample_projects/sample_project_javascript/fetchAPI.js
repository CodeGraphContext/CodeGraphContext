// Fetch API (run in browser or Node with fetch support)

fetch("https://jsonplaceholder.typicode.com/posts/1")
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(err => console.error("Error:", err));