// Try/catch error handling

try {
  throw new Error("Something went wrong!");
} catch (error) {
  console.error("Caught error:", error.message);
}