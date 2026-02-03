// Async/await syntax

const getData = async () => {
  const result = await fetchData();
  console.log("Async result:", result);
};

getData();

async function fetchData() {
  return "Fetched with async/await";
}