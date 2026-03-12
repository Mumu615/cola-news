async function loadSearchIndex() {
  const status = document.getElementById("search-status");
  const input = document.getElementById("search-input");
  const results = document.getElementById("search-results");

  try {
    const indexUrl = new URL("../data/search/index.json", window.location.href);
    const response = await fetch(indexUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("索引加载失败");
    }

    const items = await response.json();
    status.textContent = `已加载 ${items.length} 条内容，开始搜索吧。`;

    function render(list) {
      results.innerHTML = "";
      if (!list.length) {
        results.innerHTML = '<div class="search-result">没有找到匹配内容。</div>';
        return;
      }

      list.slice(0, 20).forEach((item) => {
        const tagText = Array.isArray(item.tags) ? item.tags.join(" / ") : "";
        const html = `
          <article class="search-result">
            <div class="card-topline">
              <span>${item.section || "资讯"}</span>
              <span>${item.published_at || ""}</span>
            </div>
            <h3><a href="${item.permalink}">${item.title}</a></h3>
            <p>${item.summary || ""}</p>
            <div class="meta-row">
              <span>${item.source_name || "可乐资讯"}</span>
              <span>${tagText}</span>
            </div>
          </article>
        `;
        results.insertAdjacentHTML("beforeend", html);
      });
    }

    function search(keyword) {
      const query = keyword.trim().toLowerCase();
      if (!query) {
        render(items);
        return;
      }

      const filtered = items.filter((item) => {
        const haystack = [
          item.title,
          item.summary,
          item.source_name,
          item.section,
          ...(item.tags || []),
        ]
          .join(" ")
          .toLowerCase();

        return haystack.includes(query);
      });
      render(filtered);
    }

    input.addEventListener("input", (event) => search(event.target.value));
    render(items);
  } catch (error) {
    status.textContent = error.message;
  }
}

document.addEventListener("DOMContentLoaded", loadSearchIndex);
