// Promise chaining

const fetchData = () => {
  return new Promise((resolve) => {
    setTimeout(() => resolve("Data loaded"), 1000);
  });
};

fetchData().then(data => {
  console.log(data);
});