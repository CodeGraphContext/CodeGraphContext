// Scroll Performance Optimizer - Issue #1064

let scrollTimeout: ReturnType<typeof setTimeout> | null = null;
let isScrolling = false;
let ticking = false;

const SCROLL_END_DELAY = 150;

function onScroll() {
  if (!ticking) {
    requestAnimationFrame(() => {
      handleScrollStart();
      ticking = false;
    });
    ticking = true;
  }
}

function handleScrollStart() {
  if (!isScrolling) {
    isScrolling = true;
    document.body.classList.add("is-scrolling");
  }
  clearTimeout(scrollTimeout!);
  scrollTimeout = setTimeout(handleScrollEnd, SCROLL_END_DELAY);
}

function handleScrollEnd() {
  isScrolling = false;
  document.body.classList.remove("is-scrolling");
}

function initAnimationCulling() {
  const animatedElements = document.querySelectorAll(
    '[class*="animate"], [class*="float"], [class*="pulse"], [class*="blob"]'
  );
  if (!animatedElements.length) return;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        (entry.target as HTMLElement).style.animationPlayState =
          entry.isIntersecting ? "running" : "paused";
      });
    },
    { rootMargin: "100px" }
  );
  animatedElements.forEach((el) => observer.observe(el));
}

export function initScrollPerformance() {
  window.addEventListener("scroll", onScroll, { passive: true });
  initAnimationCulling();
}

export function destroyScrollPerformance() {
  window.removeEventListener("scroll", onScroll);
  if (scrollTimeout) clearTimeout(scrollTimeout);
  document.body.classList.remove("is-scrolling");
}
