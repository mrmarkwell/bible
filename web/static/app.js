/**
 * Bible Engine — Sacred-Modern Web UI
 * Zero-dependency Vanilla JavaScript (ES6+)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const healthDot = document.getElementById("health-dot");
  const healthStatus = document.getElementById("health-status");
  const versionBadge = document.getElementById("version-badge");
  const versesBadge = document.getElementById("verses-badge");

  const inputRef = document.getElementById("input-ref");
  const btnFetchPassage = document.getElementById("btn-fetch-passage");
  const selectBook = document.getElementById("select-book");
  const selectChapter = document.getElementById("select-chapter");
  const selectVersion = document.getElementById("select-version");

  const inputSearch = document.getElementById("input-search");
  const btnSearch = document.getElementById("btn-search");
  const searchTestament = document.getElementById("search-testament");

  const inputTagFilter = document.getElementById("input-tag-filter");
  const tagCloud = document.getElementById("tag-cloud-container");

  const inputXref = document.getElementById("input-xref");
  const btnXref = document.getElementById("btn-xref");
  const xrefStatsContent = document.getElementById("xref-stats-content");

  const displayCitation = document.getElementById("display-citation");
  const displayMeta = document.getElementById("display-meta");
  const passageTags = document.getElementById("passage-tags-container");
  const scriptureContainer = document.getElementById("scripture-container");
  const crossrefSection = document.getElementById("crossref-section");
  const crossrefList = document.getElementById("crossref-list");

  let allBooks = [];
  let allTags = [];

  // -------------------------------------------------------------------------
  // Navigation & Tab Switching
  // -------------------------------------------------------------------------
  const navTabs = document.querySelectorAll(".nav-tab");
  const viewPanels = {
    passage: document.getElementById("panel-passage"),
    search: document.getElementById("panel-search"),
    topics: document.getElementById("panel-topics"),
    crossref: document.getElementById("panel-crossref"),
    api: document.getElementById("panel-api"),
  };

  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.getAttribute("data-view");
      navTabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      Object.keys(viewPanels).forEach((k) => {
        if (k === view) {
          viewPanels[k].classList.remove("hidden");
        } else {
          viewPanels[k].classList.add("hidden");
        }
      });

      if (view === "topics" && allTags.length === 0) {
        loadTags();
      } else if (view === "crossref") {
        loadCrossrefStats();
      }
    });
  });

  // -------------------------------------------------------------------------
  // Health & System Boot
  // -------------------------------------------------------------------------
  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      healthDot.style.backgroundColor = "#2ECC71";
      healthStatus.textContent = "Online";
      versesBadge.textContent = `${data.total_verses.toLocaleString()} verses`;
      if (data.translations && data.translations.length > 0) {
        versionBadge.textContent = data.translations.join(", ");
      }
    } catch (err) {
      healthDot.style.backgroundColor = "#E74C3C";
      healthStatus.textContent = "Offline";
      console.error("Health check failed:", err);
    }
  }

  // -------------------------------------------------------------------------
  // Load Books Catalog
  // -------------------------------------------------------------------------
  async function loadBooks() {
    try {
      const res = await fetch("/api/books");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      allBooks = data.books || [];

      selectBook.innerHTML = "";
      allBooks.forEach((book) => {
        const opt = document.createElement("option");
        opt.value = book.osis;
        opt.textContent = `${book.name} (${book.testament})`;
        opt.dataset.chapters = book.total_chapters;
        selectBook.appendChild(opt);
      });

      // Default to Romans
      const romIndex = allBooks.findIndex((b) => b.osis === "Rom");
      if (romIndex !== -1) {
        selectBook.selectedIndex = romIndex;
      }
      updateChapterDropdown();
    } catch (err) {
      console.error("Failed to load books catalog:", err);
    }
  }

  function updateChapterDropdown() {
    const selectedOpt = selectBook.options[selectBook.selectedIndex];
    if (!selectedOpt) return;
    const totalChapters = parseInt(selectedOpt.dataset.chapters, 10) || 1;
    selectChapter.innerHTML = "";
    for (let c = 1; c <= totalChapters; c++) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = `Chapter ${c}`;
      selectChapter.appendChild(opt);
    }
    // If Romans, default to chapter 8
    if (selectedOpt.value === "Rom") {
      selectChapter.value = "8";
    }
  }

  selectBook.addEventListener("change", () => {
    updateChapterDropdown();
    loadChapterVerses();
  });

  selectChapter.addEventListener("change", () => {
    loadChapterVerses();
  });

  async function loadChapterVerses() {
    const bookOsis = selectBook.value;
    const chapterNum = selectChapter.value;
    const version = selectVersion.value;
    inputRef.value = `${bookOsis} ${chapterNum}`;
    fetchPassage(`${bookOsis} ${chapterNum}`, version);
  }

  // -------------------------------------------------------------------------
  // Passage Fetching
  // -------------------------------------------------------------------------
  async function fetchPassage(ref, version = "WEB") {
    scriptureContainer.innerHTML = '<div class="loading-state">Loading passage...</div>';
    passageTags.innerHTML = "";
    crossrefSection.classList.add("hidden");

    try {
      const res = await fetch(`/api/passage?ref=${encodeURIComponent(ref)}&version=${encodeURIComponent(version)}`);
      const data = await res.json();

      if (!res.ok) {
        scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Error: ${data.error || "Failed to load passage."}</div>`;
        return;
      }

      displayCitation.textContent = data.reference;
      displayMeta.textContent = `${data.translation_id} · ${data.total_verses} verse${data.total_verses === 1 ? '' : 's'}${data.fallback_for ? ` (Fallback for ${data.fallback_for})` : ''}`;

      // Render Tags
      if (data.tags && data.tags.length > 0) {
        data.tags.forEach((tag) => {
          const tagSpan = document.createElement("span");
          tagSpan.className = "tag-badge";
          tagSpan.textContent = `#${tag.name}`;
          tagSpan.title = tag.description || tag.category || "";
          tagSpan.addEventListener("click", () => {
            fetchPassagesForTag(tag.name);
          });
          passageTags.appendChild(tagSpan);
        });
      }

      // Render Verses
      if (!data.verses || data.verses.length === 0) {
        scriptureContainer.innerHTML = '<div class="loading-state">No scripture text available for this passage.</div>';
        return;
      }

      scriptureContainer.innerHTML = "";
      data.verses.forEach((v) => {
        const row = document.createElement("div");
        row.className = "verse-row";
        row.innerHTML = `
          <span class="verse-num">${v.verse}</span>
          <span class="verse-text">${escapeHtml(v.text)}</span>
        `;
        scriptureContainer.appendChild(row);
      });

      // Render Cross-References if present
      if (data.cross_references && data.cross_references.length > 0) {
        crossrefSection.classList.remove("hidden");
        crossrefList.innerHTML = "";
        data.cross_references.forEach((xref) => {
          const item = document.createElement("div");
          item.className = "crossref-item";
          item.innerHTML = `
            <div class="crossref-header">
              <span class="crossref-ref">${escapeHtml(xref.target_ref)}</span>
              <span class="crossref-type">${escapeHtml(xref.relationship_type)}</span>
            </div>
          `;
          item.style.cursor = "pointer";
          item.addEventListener("click", () => {
            inputRef.value = xref.target_ref;
            fetchPassage(xref.target_ref, version);
          });
          crossrefList.appendChild(item);
        });
      }
    } catch (err) {
      scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Network error: ${err.message}</div>`;
    }
  }

  btnFetchPassage.addEventListener("click", () => {
    const ref = inputRef.value.trim();
    if (ref) {
      fetchPassage(ref, selectVersion.value);
    }
  });

  inputRef.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      btnFetchPassage.click();
    }
  });

  // Quick Chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const ref = chip.getAttribute("data-ref");
      inputRef.value = ref;
      fetchPassage(ref, selectVersion.value);
    });
  });

  // -------------------------------------------------------------------------
  // Search
  // -------------------------------------------------------------------------
  async function performSearch() {
    const q = inputSearch.value.trim();
    if (!q) return;

    scriptureContainer.innerHTML = '<div class="loading-state">Searching scriptures...</div>';
    passageTags.innerHTML = "";
    crossrefSection.classList.add("hidden");

    const testament = searchTestament.value;
    const version = selectVersion.value;
    let url = `/api/search?q=${encodeURIComponent(q)}&version=${encodeURIComponent(version)}&limit=50`;
    if (testament) url += `&testament=${encodeURIComponent(testament)}`;

    try {
      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok) {
        scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Search error: ${data.error || "Failed."}</div>`;
        return;
      }

      displayCitation.textContent = `Search: "${data.query}"`;
      displayMeta.textContent = `${data.total_matches} match${data.total_matches === 1 ? '' : 'es'} in ${version} (${testament || 'All Canon'})`;

      if (!data.results || data.results.length === 0) {
        scriptureContainer.innerHTML = '<div class="loading-state">No matching scriptures found.</div>';
        return;
      }

      scriptureContainer.innerHTML = "";
      data.results.forEach((hit) => {
        const div = document.createElement("div");
        div.className = "search-hit";
        div.innerHTML = `
          <div class="search-hit-title">${escapeHtml(hit.book)} ${hit.chapter}:${hit.verse}</div>
          <div class="search-hit-snippet">${hit.snippet || escapeHtml(hit.text)}</div>
        `;
        div.addEventListener("click", () => {
          const ref = `${hit.book} ${hit.chapter}:${hit.verse}`;
          inputRef.value = ref;
          fetchPassage(ref, version);
        });
        scriptureContainer.appendChild(div);
      });
    } catch (err) {
      scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Search failed: ${err.message}</div>`;
    }
  }

  btnSearch.addEventListener("click", performSearch);
  inputSearch.addEventListener("keydown", (e) => {
    if (e.key === "Enter") performSearch();
  });

  // -------------------------------------------------------------------------
  // Semantic Topics Cloud
  // -------------------------------------------------------------------------
  async function loadTags() {
    tagCloud.innerHTML = '<div class="loading-spinner">Loading semantic taxonomy...</div>';
    try {
      const res = await fetch("/api/tags");
      const data = await res.json();
      allTags = data.tags || [];
      renderTagCloud(allTags);
    } catch (err) {
      tagCloud.innerHTML = `<div style="color: #E74C3C;">Failed to load tags: ${err.message}</div>`;
    }
  }

  function renderTagCloud(tags) {
    tagCloud.innerHTML = "";
    if (tags.length === 0) {
      tagCloud.innerHTML = '<div style="color: var(--text-muted);">No tags match filter.</div>';
      return;
    }
    tags.forEach((tag) => {
      const el = document.createElement("span");
      el.className = "tag-badge";
      el.innerHTML = `${escapeHtml(tag.name)} <span class="count">${tag.passage_count}</span>`;
      el.addEventListener("click", () => {
        fetchPassagesForTag(tag.name);
      });
      tagCloud.appendChild(el);
    });
  }

  inputTagFilter.addEventListener("input", () => {
    const term = inputTagFilter.value.toLowerCase().trim();
    if (!term) {
      renderTagCloud(allTags);
    } else {
      const filtered = allTags.filter((t) => t.name.toLowerCase().includes(term) || (t.category && t.category.toLowerCase().includes(term)));
      renderTagCloud(filtered);
    }
  });

  async function fetchPassagesForTag(tagName) {
    scriptureContainer.innerHTML = `<div class="loading-state">Scoring verses for tag "${tagName}"...</div>`;
    displayCitation.textContent = `Topic: ${tagName}`;
    displayMeta.textContent = `Scoring verse relevance across canon...`;

    try {
      const res = await fetch(`/api/tags/relevance?tags=${encodeURIComponent(tagName)}&limit=25`);
      const data = await res.json();
      if (!res.ok || !data.results || data.results.length === 0) {
        scriptureContainer.innerHTML = `<div class="loading-state">No passages found for #${tagName}.</div>`;
        return;
      }

      displayMeta.textContent = `${data.total_results} relevant passages ranked by thematic score`;
      scriptureContainer.innerHTML = "";
      data.results.forEach((hit) => {
        const div = document.createElement("div");
        div.className = "search-hit";
        div.innerHTML = `
          <div class="search-hit-title">${escapeHtml(hit.citation)} <span style="font-size: 11px; color: var(--gold-dim); font-weight: normal;">(Score: ${(hit.score * 100).toFixed(0)}%)</span></div>
          <div class="search-hit-snippet">${escapeHtml(hit.text)}</div>
        `;
        div.addEventListener("click", () => {
          inputRef.value = hit.citation;
          fetchPassage(hit.citation);
        });
        scriptureContainer.appendChild(div);
      });
    } catch (err) {
      scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Error: ${err.message}</div>`;
    }
  }

  // -------------------------------------------------------------------------
  // Cross References Tab
  // -------------------------------------------------------------------------
  async function loadCrossrefStats() {
    try {
      const res = await fetch("/api/crossref/stats");
      const data = await res.json();
      xrefStatsContent.innerHTML = `
        <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;">Total Edges: <strong>${data.total_edges}</strong></p>
        <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;">Distinct Passages: <strong>${data.distinct_sources} sources &rarr; ${data.distinct_targets} targets</strong></p>
        <p style="font-size: 12px; color: var(--text-secondary);">Prophecy / Typology: <strong>${(data.by_relationship_type.prophecy_fulfillment || 0) + (data.by_relationship_type.typology || 0)}</strong></p>
      `;
    } catch (err) {
      xrefStatsContent.innerHTML = `<span style="color: #E74C3C;">Failed to load stats.</span>`;
    }
  }

  btnXref.addEventListener("click", async () => {
    const ref = inputXref.value.trim();
    if (!ref) return;
    try {
      const res = await fetch(`/api/crossref?ref=${encodeURIComponent(ref)}`);
      const data = await res.json();
      if (!res.ok || !data.cross_references || data.cross_references.length === 0) {
        scriptureContainer.innerHTML = `<div class="loading-state">No cross-references recorded for ${ref}.</div>`;
        return;
      }
      displayCitation.textContent = `Cross-References: ${data.reference}`;
      displayMeta.textContent = `${data.total_cross_references} relationship edge${data.total_cross_references === 1 ? '' : 's'}`;
      scriptureContainer.innerHTML = "";
      data.cross_references.forEach((xref) => {
        const div = document.createElement("div");
        div.className = "crossref-item";
        div.innerHTML = `
          <div class="crossref-header">
            <span class="crossref-ref">${escapeHtml(xref.target_ref)}</span>
            <span class="crossref-type">${escapeHtml(xref.relationship_type)}</span>
          </div>
          ${xref.target_text ? `<div class="crossref-text">"${escapeHtml(xref.target_text)}"</div>` : ''}
        `;
        div.style.cursor = "pointer";
        div.addEventListener("click", () => {
          inputRef.value = xref.target_ref;
          fetchPassage(xref.target_ref);
        });
        scriptureContainer.appendChild(div);
      });
    } catch (err) {
      scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Failed: ${err.message}</div>`;
    }
  });

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initial Boot
  checkHealth();
  loadBooks();
  fetchPassage("Romans 8:28-39", "WEB");
});
