/**
 * Bible Engine — Sacred-Modern Web UI
 * Zero-dependency Vanilla JavaScript (ES6+)
 * 
 * Implements:
 * - Sacred-Modern Obsidian/Scriptorium/Monastery Theme Engine
 * - Dynamic Typography Scaling & Flow/List Reader Modes
 * - One-Click Passage Copy with Theological Citation
 * - Responsive Split-Pane & Collapsible Zen Reading Sidebar
 * - Canonical Ribbon 66-Book Visual Navigator
 * - Global Header Quick Reference & Search Preprocessor
 * - Keyboard Shortcut Subsystem (/ , [ , f , + , - , t , c , ? , Esc)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements - Header & Status
  const healthDot = document.getElementById("health-dot");
  const healthStatus = document.getElementById("health-status");
  const versionBadge = document.getElementById("version-badge");
  const versesBadge = document.getElementById("verses-badge");
  const selectTheme = document.getElementById("select-theme");
  const btnFontDec = document.getElementById("btn-font-dec");
  const btnFontInc = document.getElementById("btn-font-inc");
  const btnToggleFlow = document.getElementById("btn-toggle-flow");
  const btnShortcuts = document.getElementById("btn-shortcuts");
  const headerQuickInput = document.getElementById("header-quick-input");

  // DOM Elements - Sidebar & Layout
  const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
  const sidebar = document.getElementById("sidebar");
  const sidebarOverlay = document.getElementById("sidebar-overlay");

  // DOM Elements - Passage Tab
  const inputRef = document.getElementById("input-ref");
  const btnFetchPassage = document.getElementById("btn-fetch-passage");
  const selectBook = document.getElementById("select-book");
  const selectChapter = document.getElementById("select-chapter");
  const selectVersion = document.getElementById("select-version");

  // DOM Elements - Search Tab
  const inputSearch = document.getElementById("input-search");
  const btnSearch = document.getElementById("btn-search");
  const searchTestament = document.getElementById("search-testament");
  const searchStatsBar = document.getElementById("search-stats-bar");
  const searchResultsCount = document.getElementById("search-results-count");
  const searchResultsList = document.getElementById("search-results-list");

  // DOM Elements - Topics Tab
  const inputTagFilter = document.getElementById("input-tag-filter");
  const categoryFilterBar = document.getElementById("category-filter-bar");
  const tagCloud = document.getElementById("tag-cloud-container");

  // DOM Elements - Crossref Tab
  const inputXref = document.getElementById("input-xref");
  const btnXref = document.getElementById("btn-xref");
  const xrefStatsContent = document.getElementById("xref-stats-content");

  // DOM Elements - Ribbon Tab & Drill-Down
  const selectRibbonTag = document.getElementById("select-ribbon-tag");
  const otBookGrid = document.getElementById("ot-book-grid");
  const ntBookGrid = document.getElementById("nt-book-grid");
  const canonOverviewContainer = document.getElementById("canon-overview-container");
  const chapterDrilldownBox = document.getElementById("chapter-drilldown-box");
  const btnBackToCanon = document.getElementById("btn-back-to-canon");
  const drilldownBookTitle = document.getElementById("drilldown-book-title");
  const drilldownBookSubtitle = document.getElementById("drilldown-book-subtitle");
  const drilldownChapterGrid = document.getElementById("drilldown-chapter-grid");

  // DOM Elements - Reader Stage
  const displayCitation = document.getElementById("display-citation");
  const displayMeta = document.getElementById("display-meta");
  const passageTags = document.getElementById("passage-tags-container");
  const pericopeNavBar = document.getElementById("pericope-nav-bar");
  const pericopeChips = document.getElementById("pericope-chips");
  const scriptureContainer = document.getElementById("scripture-container");
  const btnPrevChapter = document.getElementById("btn-prev-chapter");
  const btnNextChapter = document.getElementById("btn-next-chapter");
  const prevChapterLabel = document.getElementById("prev-chapter-label");
  const nextChapterLabel = document.getElementById("next-chapter-label");
  const bcTestament = document.getElementById("bc-testament");
  const bcBook = document.getElementById("bc-book");
  const bcChapter = document.getElementById("bc-chapter");
  const btnCopyPassage = document.getElementById("btn-copy-passage");
  const btnToggleNumbers = document.getElementById("btn-toggle-numbers");
  const verseNumbersLabel = document.getElementById("verse-numbers-label");
  const crossrefSection = document.getElementById("crossref-section");
  const crossrefList = document.getElementById("crossref-list");
  const crossrefCountBadge = document.getElementById("crossref-count-badge");

  // DOM Elements - Arcs Tab & Panoramic Stage
  const selectArcType = document.getElementById("select-arc-type");
  const selectArcBook = document.getElementById("select-arc-book");
  const selectArcScope = document.getElementById("select-arc-scope");
  const arcStatsSidebarContent = document.getElementById("arc-stats-sidebar-content");
  const arcSidebarCountPill = document.getElementById("arc-sidebar-count-pill");
  const arcSidebarList = document.getElementById("arc-sidebar-list");
  const arcVisualizerStage = document.getElementById("arc-visualizer-stage");
  const arcSvgViewport = document.getElementById("arc-svg-viewport");
  const btnStageDownloadSvg = document.getElementById("btn-stage-download-svg");
  const arcActiveDetailCard = document.getElementById("arc-active-detail-card");
  const arcCardType = document.getElementById("arc-card-type");
  const arcCardDistance = document.getElementById("arc-card-distance");
  const arcCardSource = document.getElementById("arc-card-source");
  const arcCardTarget = document.getElementById("arc-card-target");
  const arcCardNotes = document.getElementById("arc-card-notes");
  const btnReadArcPassage = document.getElementById("btn-read-arc-passage");

  // Modals & Toast
  const shortcutsModal = document.getElementById("shortcuts-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const toast = document.getElementById("toast");

  // State
  let arcNetworkData = null;
  let activeArcId = null;
  let allBooks = [];
  let allTags = [];
  let currentPassageData = null;
  let activeTagCategory = "";
  let currentFontSize = parseInt(localStorage.getItem("bible_font_size"), 10) || 19;
  let isFlowMode = localStorage.getItem("bible_flow_mode") === "true";
  let showVerseNumbers = localStorage.getItem("bible_show_numbers") !== "false";
  let ribbonDensityMap = {};

  // -------------------------------------------------------------------------
  // Sacred-Modern Theme Engine
  // -------------------------------------------------------------------------
  const savedTheme = localStorage.getItem("bible_theme") || "obsidian";
  setTheme(savedTheme);

  selectTheme.addEventListener("change", (e) => {
    setTheme(e.target.value);
  });

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("bible_theme", theme);
    if (selectTheme.value !== theme) {
      selectTheme.value = theme;
    }
  }

  function cycleTheme() {
    const themes = ["obsidian", "scriptorium", "monastery"];
    const current = document.documentElement.getAttribute("data-theme") || "obsidian";
    const next = themes[(themes.indexOf(current) + 1) % themes.length];
    setTheme(next);
    showToast(`Theme: ${next.charAt(0).toUpperCase() + next.slice(1)}`);
  }

  // -------------------------------------------------------------------------
  // Typography Scaling & Reader Controls
  // -------------------------------------------------------------------------
  applyTypography();

  btnFontDec.addEventListener("click", () => {
    if (currentFontSize > 15) {
      currentFontSize -= 1;
      applyTypography();
    }
  });

  btnFontInc.addEventListener("click", () => {
    if (currentFontSize < 30) {
      currentFontSize += 1;
      applyTypography();
    }
  });

  function applyTypography() {
    document.documentElement.style.setProperty("--reader-font-size", `${currentFontSize}px`);
    localStorage.setItem("bible_font_size", currentFontSize);
  }

  // Flow Mode Toggle
  if (isFlowMode) {
    scriptureContainer.classList.add("flow-mode");
    btnToggleFlow.classList.add("active");
  }

  btnToggleFlow.addEventListener("click", toggleFlowMode);

  function toggleFlowMode() {
    isFlowMode = !isFlowMode;
    scriptureContainer.classList.toggle("flow-mode", isFlowMode);
    btnToggleFlow.classList.toggle("active", isFlowMode);
    localStorage.setItem("bible_flow_mode", isFlowMode);
    showToast(isFlowMode ? "Paragraph Flow Mode" : "Verse List Mode");
  }

  // Verse Numbers Toggle
  if (!showVerseNumbers) {
    scriptureContainer.classList.add("hide-numbers");
    verseNumbersLabel.textContent = "Numbers: Off";
  }

  btnToggleNumbers.addEventListener("click", () => {
    showVerseNumbers = !showVerseNumbers;
    scriptureContainer.classList.toggle("hide-numbers", !showVerseNumbers);
    verseNumbersLabel.textContent = showVerseNumbers ? "Numbers: On" : "Numbers: Off";
    localStorage.setItem("bible_show_numbers", showVerseNumbers);
  });

  // -------------------------------------------------------------------------
  // Sidebar Collapse & Mobile Drawer
  // -------------------------------------------------------------------------
  btnToggleSidebar.addEventListener("click", toggleSidebar);
  sidebarOverlay.addEventListener("click", closeMobileSidebar);

  function toggleSidebar() {
    if (window.innerWidth <= 900) {
      sidebar.classList.toggle("open");
      sidebarOverlay.classList.toggle("active", sidebar.classList.contains("open"));
    } else {
      sidebar.classList.toggle("collapsed");
    }
  }

  function closeMobileSidebar() {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("active");
  }

  // -------------------------------------------------------------------------
  // Navigation & Tab Switching
  // -------------------------------------------------------------------------
  const navTabs = document.querySelectorAll(".nav-tab");
  const viewPanels = {
    passage: document.getElementById("panel-passage"),
    search: document.getElementById("panel-search"),
    topics: document.getElementById("panel-topics"),
    crossref: document.getElementById("panel-crossref"),
    ribbon: document.getElementById("panel-ribbon"),
    arcs: document.getElementById("panel-arcs"),
    api: document.getElementById("panel-api"),
  };

  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.getAttribute("data-view");
      navTabs.forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");

      Object.keys(viewPanels).forEach((k) => {
        if (k === view) {
          viewPanels[k].classList.remove("hidden");
        } else {
          viewPanels[k].classList.add("hidden");
        }
      });

      // Toggle Reader Stage vs. Panoramic Arc Stage
      const chapterNavBar = document.querySelector(".chapter-nav-bar");
      const stageHeader = document.querySelector(".stage-header");
      const scriptureViewport = document.querySelector(".scripture-viewport");

      if (view === "arcs") {
        if (chapterNavBar) chapterNavBar.classList.add("hidden");
        if (stageHeader) stageHeader.classList.add("hidden");
        if (passageTags) passageTags.classList.add("hidden");
        if (pericopeNavBar) pericopeNavBar.classList.add("hidden");
        if (scriptureViewport) scriptureViewport.classList.add("hidden");
        if (crossrefSection) crossrefSection.classList.add("hidden");
        if (arcVisualizerStage) arcVisualizerStage.classList.remove("hidden");

        populateArcBookSelector();
        loadArcNetwork();
      } else {
        if (chapterNavBar) chapterNavBar.classList.remove("hidden");
        if (stageHeader) stageHeader.classList.remove("hidden");
        if (passageTags) passageTags.classList.remove("hidden");
        if (scriptureViewport) scriptureViewport.classList.remove("hidden");
        if (arcVisualizerStage) arcVisualizerStage.classList.add("hidden");
      }

      if (view === "topics" && allTags.length === 0) {
        loadTags();
      } else if (view === "crossref") {
        loadCrossrefStats();
      } else if (view === "ribbon") {
        if (allTags.length === 0) {
          loadTags().then(() => populateRibbonTagSelector());
        } else {
          populateRibbonTagSelector();
        }
        if (Object.keys(ribbonDensityMap).length === 0) {
          loadRibbonDensity();
        } else {
          renderCanonicalRibbon();
        }
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
  // Books Catalog & Canonical Ribbon
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
        opt.dataset.testament = book.testament;
        opt.dataset.name = book.name;
        selectBook.appendChild(opt);
      });

      // Default to Romans
      const romIndex = allBooks.findIndex((b) => b.osis === "Rom");
      if (romIndex !== -1) {
        selectBook.selectedIndex = romIndex;
      }
      updateChapterDropdown();
      renderCanonicalRibbon();
    } catch (err) {
      console.error("Failed to load books catalog:", err);
    }
  }

  async function loadRibbonDensity(tagName = "") {
    try {
      let url = "/api/tags/density";
      if (tagName) url += `?tag=${encodeURIComponent(tagName)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      ribbonDensityMap = {};
      (data.densities || []).forEach((d) => {
        ribbonDensityMap[d.book_id] = d;
      });
      renderCanonicalRibbon();
    } catch (err) {
      console.error("Failed to load ribbon density:", err);
      renderCanonicalRibbon();
    }
  }

  function populateRibbonTagSelector() {
    if (!allTags || allTags.length === 0) return;
    const currentVal = selectRibbonTag.value;
    selectRibbonTag.innerHTML = '<option value="">★ All Canonical Topics (Composite Density)</option>';
    allTags.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.name;
      opt.textContent = `#${t.name} (${t.passage_count || 0} passages)`;
      selectRibbonTag.appendChild(opt);
    });
    selectRibbonTag.value = currentVal;
  }

  selectRibbonTag.addEventListener("change", () => {
    loadRibbonDensity(selectRibbonTag.value);
    if (activeDrilldownBook) {
      showChapterDrilldown(activeDrilldownBook);
    }
  });

  let activeDrilldownBook = null;

  function renderCanonicalRibbon() {
    if (!allBooks || allBooks.length === 0) return;
    otBookGrid.innerHTML = "";
    ntBookGrid.innerHTML = "";

    // Find max passage count for proportional heat scaling
    let maxPassages = 1;
    Object.values(ribbonDensityMap).forEach((d) => {
      if (d.passage_count > maxPassages) maxPassages = d.passage_count;
    });

    allBooks.forEach((book) => {
      const btn = document.createElement("button");
      btn.className = "canon-book-btn";
      
      const density = ribbonDensityMap[book.number] || ribbonDensityMap[book.id];
      const count = density ? density.passage_count : 0;
      const starred = density ? density.starred_count : 0;
      const pct = maxPassages > 0 ? (count / maxPassages) : 0;

      // Assign heat level (0 to 4)
      let heat = 0;
      if (count > 0) {
        if (pct >= 0.85) heat = 4;
        else if (pct >= 0.60) heat = 3;
        else if (pct >= 0.25) heat = 2;
        else heat = 1;
      }
      btn.dataset.heat = heat;

      const starIndicator = starred > 0 ? " ★" : "";
      btn.innerHTML = `<span>${escapeHtml(book.osis)}</span><span class="book-heat-badge">${count > 0 ? count + starIndicator : ''}</span>`;
      btn.title = `${book.name} (${book.total_chapters} ch)\n${count} tagged passage${count === 1 ? '' : 's'}${starred > 0 ? ` (${starred} starred)` : ''}\nClick to view chapter heatmap & drill down`;

      btn.addEventListener("click", () => {
        showChapterDrilldown(book);
      });
      if (book.testament === "OT") {
        otBookGrid.appendChild(btn);
      } else {
        ntBookGrid.appendChild(btn);
      }
    });
  }

  async function showChapterDrilldown(book) {
    if (!book) return;
    activeDrilldownBook = book;
    canonOverviewContainer.classList.add("hidden");
    chapterDrilldownBox.classList.remove("hidden");

    drilldownBookTitle.textContent = book.name;
    const currentTag = selectRibbonTag.value;
    drilldownBookSubtitle.textContent = `${book.total_chapters} Chapters · ${currentTag ? `#${currentTag}` : 'Composite Topic Density'}`;
    drilldownChapterGrid.innerHTML = '<div class="loading-spinner">Loading chapter density...</div>';

    selectBook.value = book.osis;
    updateChapterDropdown();

    try {
      let url = `/api/tags/chapters?book=${encodeURIComponent(book.osis)}`;
      if (currentTag) url += `&tag=${encodeURIComponent(currentTag)}`;
      const res = await fetch(url);
      const data = await res.json();
      const chapters = data.chapters || [];

      let maxChPassages = 1;
      chapters.forEach((ch) => {
        if (ch.passage_count > maxChPassages) maxChPassages = ch.passage_count;
      });

      drilldownChapterGrid.innerHTML = "";
      for (let c = 1; c <= book.total_chapters; c++) {
        const chData = chapters.find((ch) => ch.chapter === c);
        const count = chData ? chData.passage_count : 0;
        const starred = chData ? chData.starred_count : 0;
        const pct = maxChPassages > 0 ? (count / maxChPassages) : 0;

        let heat = 0;
        if (count > 0) {
          if (pct >= 0.85) heat = 4;
          else if (pct >= 0.60) heat = 3;
          else if (pct >= 0.25) heat = 2;
          else heat = 1;
        }

        const chBtn = document.createElement("button");
        chBtn.className = "drilldown-chapter-btn";
        chBtn.dataset.heat = heat;
        chBtn.dataset.chapter = c;
        if (selectChapter.value == c && selectBook.value === book.osis) {
          chBtn.classList.add("active");
        }

        const starStr = starred > 0 ? "★" : "";
        chBtn.innerHTML = `<span>${c}</span><span class="chapter-heat-badge">${count > 0 ? count + starStr : ''}</span>`;
        chBtn.title = `${book.name} Chapter ${c}\n${count} tagged passage${count === 1 ? '' : 's'}${starred > 0 ? ` (${starred} starred)` : ''}`;

        chBtn.addEventListener("click", () => {
          document.querySelectorAll(".drilldown-chapter-btn").forEach((b) => b.classList.remove("active"));
          chBtn.classList.add("active");
          selectChapter.value = c;
          inputRef.value = `${book.osis} ${c}`;
          fetchPassage(`${book.osis} ${c}`, selectVersion.value);
          closeMobileSidebar();
        });

        drilldownChapterGrid.appendChild(chBtn);
      }
    } catch (err) {
      console.error("Failed to load chapter density:", err);
      drilldownChapterGrid.innerHTML = "";
      for (let c = 1; c <= book.total_chapters; c++) {
        const chBtn = document.createElement("button");
        chBtn.className = "drilldown-chapter-btn";
        chBtn.textContent = c;
        chBtn.addEventListener("click", () => {
          selectChapter.value = c;
          inputRef.value = `${book.osis} ${c}`;
          fetchPassage(`${book.osis} ${c}`, selectVersion.value);
          closeMobileSidebar();
        });
        drilldownChapterGrid.appendChild(chBtn);
      }
    }
  }

  btnBackToCanon.addEventListener("click", () => {
    activeDrilldownBook = null;
    chapterDrilldownBox.classList.add("hidden");
    canonOverviewContainer.classList.remove("hidden");
  });

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
  // Scripture Passage Fetching & Formatting
  // -------------------------------------------------------------------------
  async function fetchPassage(ref, version = "WEB") {
    scriptureContainer.innerHTML = '<div class="loading-state">Loading passage...</div>';
    passageTags.innerHTML = "";
    pericopeNavBar.classList.add("hidden");
    pericopeChips.innerHTML = "";
    crossrefSection.classList.add("hidden");

    try {
      const res = await fetch(`/api/passage?ref=${encodeURIComponent(ref)}&version=${encodeURIComponent(version)}`);
      const data = await res.json();

      if (!res.ok) {
        scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Error: ${data.error || "Failed to load passage."}</div>`;
        return;
      }

      currentPassageData = data;
      displayCitation.textContent = data.reference;
      displayMeta.textContent = `${data.translation_id} · ${data.total_verses} verse${data.total_verses === 1 ? '' : 's'}${data.fallback_for ? ` (Fallback for ${data.fallback_for})` : ''}`;

      // Update Breadcrumbs & Chapter Nav
      updateBreadcrumbsAndNav(data);

      // Render Semantic Tags with Categories
      if (data.tags && data.tags.length > 0) {
        data.tags.forEach((tag) => {
          const tagSpan = document.createElement("span");
          tagSpan.className = "tag-badge";
          if (tag.category) tagSpan.dataset.category = tag.category.toLowerCase();
          tagSpan.textContent = `#${tag.name}`;
          tagSpan.title = `${tag.category ? `[${tag.category}] ` : ""}${tag.notes || tag.description || ""}`;
          tagSpan.addEventListener("click", () => {
            fetchPassagesForTag(tag.name);
          });
          passageTags.appendChild(tagSpan);
        });
      }

      // Render Pericope Navigation Bar Chips
      if (data.pericopes && data.pericopes.length > 0) {
        pericopeNavBar.classList.remove("hidden");
        pericopeChips.innerHTML = "";
        data.pericopes.forEach((p) => {
          const chip = document.createElement("div");
          chip.className = "pericope-nav-chip";
          chip.innerHTML = `<span>${escapeHtml(p.title)}</span><span class="chip-ref">${escapeHtml(p.human_ref)}</span>`;
          chip.title = `${p.title}\n${p.human_ref}\n${p.redemptive_summary || ""}`;
          chip.addEventListener("click", () => {
            const bannerEl = document.getElementById(`pericope-${p.id}`);
            if (bannerEl) {
              bannerEl.scrollIntoView({ behavior: "smooth", block: "center" });
              bannerEl.classList.add("highlighted");
              setTimeout(() => bannerEl.classList.remove("highlighted"), 2200);
            }
          });
          pericopeChips.appendChild(chip);
        });
      }

      // Render Verses with Pericope Section Banners
      if (!data.verses || data.verses.length === 0) {
        scriptureContainer.innerHTML = '<div class="loading-state">No scripture text available for this passage.</div>';
        return;
      }

      scriptureContainer.innerHTML = "";
      data.verses.forEach((v, index) => {
        // Check for starting pericopes at this verse boundary
        const startingPericopes = (data.pericopes || []).filter((p) => {
          if (p.start_canonical_id === v.canonical_verse_id) return true;
          return index === 0 && v.canonical_verse_id >= p.start_canonical_id && v.canonical_verse_id <= p.end_canonical_id;
        });

        startingPericopes.forEach((p) => {
          const banner = document.createElement("div");
          banner.className = "pericope-banner";
          banner.id = `pericope-${p.id}`;
          banner.innerHTML = `
            <div class="pericope-banner-header">
              <span class="pericope-title">✦ ${escapeHtml(p.title)}</span>
              <span class="pericope-ref">${escapeHtml(p.human_ref)}</span>
            </div>
            ${p.redemptive_summary ? `<div class="pericope-summary">${escapeHtml(p.redemptive_summary)}</div>` : ""}
          `;
          scriptureContainer.appendChild(banner);
        });

        const row = document.createElement("div");
        row.className = "verse-row";
        row.dataset.verseNum = v.verse;
        row.id = `v${v.verse}`;

        const tagPills = (v.tags && v.tags.length > 0)
          ? v.tags.map((t) => `<span class="verse-tag-pill" data-tag="${escapeHtml(t)}">#${escapeHtml(t)}</span>`).join("")
          : "";

        row.innerHTML = `
          <span class="verse-num">${v.verse}</span>
          <span class="verse-text">${escapeHtml(v.text)}${tagPills}</span>
        `;

        row.querySelectorAll(".verse-tag-pill").forEach((pill) => {
          pill.addEventListener("click", (e) => {
            e.stopPropagation();
            const tName = pill.getAttribute("data-tag");
            if (tName) fetchPassagesForTag(tName);
          });
        });

        scriptureContainer.appendChild(row);
      });

      // Render Cross-References if present
      if (data.cross_references && data.cross_references.length > 0) {
        crossrefSection.classList.remove("hidden");
        crossrefCountBadge.textContent = `${data.cross_references.length} edge${data.cross_references.length === 1 ? '' : 's'}`;
        crossrefList.innerHTML = "";
        data.cross_references.forEach((xref) => {
          const item = document.createElement("div");
          item.className = "crossref-item";
          item.innerHTML = `
            <div class="crossref-header">
              <span class="crossref-ref">${escapeHtml(xref.target_ref)}</span>
              <span class="crossref-type">${escapeHtml(xref.relationship_type)}</span>
            </div>
            ${xref.notes ? `<div class="crossref-text">${escapeHtml(xref.notes)}</div>` : ''}
          `;
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

  function updateBreadcrumbsAndNav(data) {
    if (!allBooks || allBooks.length === 0) return;

    // Detect book and chapter from first verse
    const firstVerse = data.verses && data.verses[0];
    if (!firstVerse) return;

    const bookObj = allBooks.find((b) => b.name.toLowerCase() === firstVerse.book.toLowerCase() || b.osis.toLowerCase() === firstVerse.book.toLowerCase());
    if (!bookObj) return;

    bcTestament.textContent = bookObj.testament === "OT" ? "Old Testament" : "New Testament";
    bcBook.textContent = bookObj.name;
    bcChapter.textContent = `Chapter ${firstVerse.chapter}`;

    // Compute previous and next chapter targets
    const currentBookIdx = allBooks.findIndex((b) => b.osis === bookObj.osis);
    const currentChapter = firstVerse.chapter;
    const totalChapters = bookObj.total_chapters;

    // Previous
    if (currentChapter > 1) {
      btnPrevChapter.dataset.target = `${bookObj.osis} ${currentChapter - 1}`;
      prevChapterLabel.textContent = `Ch ${currentChapter - 1}`;
      btnPrevChapter.disabled = false;
    } else if (currentBookIdx > 0) {
      const prevBook = allBooks[currentBookIdx - 1];
      btnPrevChapter.dataset.target = `${prevBook.osis} ${prevBook.total_chapters}`;
      prevChapterLabel.textContent = `${prevBook.osis} ${prevBook.total_chapters}`;
      btnPrevChapter.disabled = false;
    } else {
      btnPrevChapter.disabled = true;
      prevChapterLabel.textContent = "Beginning";
    }

    // Next
    if (currentChapter < totalChapters) {
      btnNextChapter.dataset.target = `${bookObj.osis} ${currentChapter + 1}`;
      nextChapterLabel.textContent = `Ch ${currentChapter + 1}`;
      btnNextChapter.disabled = false;
    } else if (currentBookIdx < allBooks.length - 1) {
      const nextBook = allBooks[currentBookIdx + 1];
      btnNextChapter.dataset.target = `${nextBook.osis} 1`;
      nextChapterLabel.textContent = `${nextBook.osis} 1`;
      btnNextChapter.disabled = false;
    } else {
      btnNextChapter.disabled = true;
      nextChapterLabel.textContent = "End";
    }
  }

  btnPrevChapter.addEventListener("click", () => {
    if (btnPrevChapter.dataset.target) {
      inputRef.value = btnPrevChapter.dataset.target;
      fetchPassage(btnPrevChapter.dataset.target, selectVersion.value);
    }
  });

  btnNextChapter.addEventListener("click", () => {
    if (btnNextChapter.dataset.target) {
      inputRef.value = btnNextChapter.dataset.target;
      fetchPassage(btnNextChapter.dataset.target, selectVersion.value);
    }
  });

  btnFetchPassage.addEventListener("click", () => {
    const ref = inputRef.value.trim();
    if (ref) {
      fetchPassage(ref, selectVersion.value);
      closeMobileSidebar();
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
      closeMobileSidebar();
    });
  });

  // One-Click Passage Copy
  btnCopyPassage.addEventListener("click", copyCurrentPassage);

  function copyCurrentPassage() {
    if (!currentPassageData || !currentPassageData.verses || currentPassageData.verses.length === 0) {
      showToast("No passage loaded to copy.");
      return;
    }

    const citation = currentPassageData.reference;
    const version = currentPassageData.translation_id || "WEB";
    const lines = [`${citation} (${version})`];

    currentPassageData.verses.forEach((v) => {
      lines.push(`[${v.verse}] ${v.text}`);
    });

    const fullText = lines.join("\n");
    navigator.clipboard.writeText(fullText).then(
      () => {
        showToast(`Copied ${citation} to clipboard!`);
      },
      () => {
        showToast("Clipboard copy failed.");
      }
    );
  }

  // -------------------------------------------------------------------------
  // Header Quick Input Preprocessor
  // -------------------------------------------------------------------------
  headerQuickInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const q = headerQuickInput.value.trim();
      if (!q) return;

      // If starts with number or standard book pattern, treat as passage lookup
      const isCitation = /^[1-3]?\s*[A-Za-z]+(\s+\d+|\s*\d+:\d+)/i.test(q);
      if (isCitation) {
        inputRef.value = q;
        fetchPassage(q, selectVersion.value);
      } else {
        // Otherwise full-text search
        inputSearch.value = q;
        const searchTab = document.querySelector('.nav-tab[data-view="search"]');
        if (searchTab) searchTab.click();
        performSearch();
      }
      headerQuickInput.blur();
    }
  });

  // -------------------------------------------------------------------------
  // Search (SQLite FTS5)
  // -------------------------------------------------------------------------
  async function performSearch() {
    const q = inputSearch.value.trim();
    if (!q) return;

    scriptureContainer.innerHTML = '<div class="loading-state">Searching scriptures with SQLite FTS5...</div>';
    passageTags.innerHTML = "";
    crossrefSection.classList.add("hidden");
    searchStatsBar.classList.remove("hidden");
    searchResultsCount.textContent = "Searching...";

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
      searchResultsCount.textContent = `${data.total_matches} match${data.total_matches === 1 ? '' : 'es'}`;

      if (!data.results || data.results.length === 0) {
        scriptureContainer.innerHTML = '<div class="loading-state">No matching scriptures found.</div>';
        searchResultsList.innerHTML = "";
        return;
      }

      scriptureContainer.innerHTML = "";
      searchResultsList.innerHTML = "";

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
          closeMobileSidebar();
        });

        // Add to main stage and sidebar list
        scriptureContainer.appendChild(div.cloneNode(true));
        searchResultsList.appendChild(div);
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
  // Semantic Topics & Taxonomy Cloud
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
    const term = inputTagFilter.value.toLowerCase().trim();

    let filtered = tags;
    if (activeTagCategory) {
      filtered = filtered.filter((t) => t.category && t.category.toLowerCase() === activeTagCategory.toLowerCase());
    }
    if (term) {
      filtered = filtered.filter((t) => t.name.toLowerCase().includes(term) || (t.category && t.category.toLowerCase().includes(term)));
    }

    if (filtered.length === 0) {
      tagCloud.innerHTML = '<div style="color: var(--text-muted); font-size: 12px;">No matching semantic tags.</div>';
      return;
    }

    filtered.forEach((tag) => {
      const el = document.createElement("span");
      el.className = "tag-badge";
      if (tag.category) el.dataset.category = tag.category.toLowerCase();
      el.innerHTML = `${escapeHtml(tag.name)} <span class="count">${tag.passage_count}</span>`;
      el.title = `${tag.category ? `[${tag.category}] ` : ""}${tag.description || ""}`;
      el.addEventListener("click", () => {
        fetchPassagesForTag(tag.name);
        closeMobileSidebar();
      });
      tagCloud.appendChild(el);
    });
  }

  inputTagFilter.addEventListener("input", () => renderTagCloud(allTags));

  categoryFilterBar.querySelectorAll(".filter-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      categoryFilterBar.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeTagCategory = pill.dataset.cat || "";
      renderTagCloud(allTags);
    });
  });

  async function fetchPassagesForTag(tagName) {
    scriptureContainer.innerHTML = `<div class="loading-state">Scoring verses for tag "${tagName}"...</div>`;
    displayCitation.textContent = `Topic: #${tagName}`;
    displayMeta.textContent = `Scoring verse relevance across canon...`;

    try {
      const res = await fetch(`/api/tags/relevance?tags=${encodeURIComponent(tagName)}&limit=25`);
      const data = await res.json();
      if (!res.ok || !data.results || data.results.length === 0) {
        scriptureContainer.innerHTML = `<div class="loading-state">No passages found for #${tagName}.</div>`;
        return;
      }

      displayMeta.textContent = `${data.total_results} relevant passages ranked by theological score`;
      scriptureContainer.innerHTML = "";
      data.results.forEach((hit) => {
        const div = document.createElement("div");
        div.className = "search-hit";
        div.innerHTML = `
          <div class="search-hit-title">${escapeHtml(hit.citation)} <span style="font-size: 11px; color: var(--gold-dim); font-weight: normal;">(${(hit.score * 100).toFixed(0)}% match)</span></div>
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
          ${xref.notes ? `<div class="crossref-text">${escapeHtml(xref.notes)}</div>` : ''}
          ${xref.target_text ? `<div class="crossref-text">"${escapeHtml(xref.target_text)}"</div>` : ''}
        `;
        div.addEventListener("click", () => {
          inputRef.value = xref.target_ref;
          fetchPassage(xref.target_ref);
          closeMobileSidebar();
        });
        scriptureContainer.appendChild(div);
      });
    } catch (err) {
      scriptureContainer.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Failed: ${escapeHtml(err.message)}</div>`;
    }
  });

  // -------------------------------------------------------------------------
  // Typological Arc Network & Cross-Reference Graph Subsystem
  // -------------------------------------------------------------------------
  function populateArcBookSelector() {
    if (!selectArcBook || selectArcBook.children.length > 1) return;
    selectArcBook.innerHTML = '<option value="" selected>All 66 Canonical Books</option>';
    allBooks.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b.name;
      opt.textContent = `${b.number}. ${b.name} (${b.testament})`;
      selectArcBook.appendChild(opt);
    });
  }

  function getActiveThemeName() {
    const rootTheme = document.documentElement.getAttribute("data-theme") || "obsidian";
    if (rootTheme === "scriptorium") return "scriptorium";
    if (rootTheme === "monastery") return "monastery";
    return "obsidian";
  }

  async function loadArcNetwork() {
    const relType = selectArcType ? selectArcType.value : "";
    const book = selectArcBook ? selectArcBook.value : "";
    const scope = selectArcScope ? selectArcScope.value : "OT-NT";
    const theme = getActiveThemeName();

    const params = new URLSearchParams();
    if (relType) params.append("type", relType);
    if (book) params.append("book", book);
    if (scope) params.append("testament", scope);
    params.append("theme", theme);
    params.append("width", "1200");
    params.append("height", "520");

    try {
      arcSvgViewport.innerHTML = `<div class="loading-state">Generating Typological Arc Network vector geometry...</div>`;

      const [jsonRes, svgRes] = await Promise.all([
        fetch(`/api/crossref/arcs?${params.toString()}`),
        fetch(`/api/crossref/arcs.svg?${params.toString()}`)
      ]);

      if (!jsonRes.ok || !svgRes.ok) throw new Error("Failed to fetch arc network");

      arcNetworkData = await jsonRes.json();
      const svgText = await svgRes.text();

      arcSvgViewport.innerHTML = svgText;

      if (arcStatsSidebarContent) {
        const typeBreakdown = Object.entries(arcNetworkData.connections_by_type || {})
          .map(([k, v]) => `<span>${k}: <strong>${v}</strong></span>`)
          .join(" · ");
        arcStatsSidebarContent.innerHTML = `
          <p style="font-size: 12.5px; color: var(--text-primary); margin-bottom: 4px;">
            <strong>${arcNetworkData.total_connections}</strong> canonical connections (${arcNetworkData.ot_to_nt_count} OT ➔ NT)
          </p>
          <div style="font-size: 11px; color: var(--text-muted); line-height: 1.5;">${typeBreakdown}</div>
        `;
      }

      if (arcSidebarCountPill) {
        arcSidebarCountPill.textContent = arcNetworkData.total_connections;
      }

      renderArcSidebarList(arcNetworkData.arcs || []);
      wireSvgArcInteractions();

      if (arcNetworkData.arcs && arcNetworkData.arcs.length > 0) {
        inspectArc(arcNetworkData.arcs[0]);
      }
    } catch (err) {
      arcSvgViewport.innerHTML = `<div class="loading-state" style="color: #E74C3C;">Failed to load Arc Network: ${escapeHtml(err.message)}</div>`;
    }
  }

  function wireSvgArcInteractions() {
    const paths = arcSvgViewport.querySelectorAll(".arc-path");
    paths.forEach((path) => {
      path.addEventListener("mouseenter", () => {
        const arcId = parseInt(path.getAttribute("data-id"), 10);
        const arc = (arcNetworkData.arcs || []).find((a) => a.id === arcId);
        if (arc) inspectArc(arc);
      });

      path.addEventListener("click", () => {
        const arcId = parseInt(path.getAttribute("data-id"), 10);
        const arc = (arcNetworkData.arcs || []).find((a) => a.id === arcId);
        if (arc) {
          inspectArc(arc);
          highlightSidebarArc(arcId);
        }
      });
    });
  }

  function inspectArc(arc) {
    if (!arc) return;
    activeArcId = arc.id;

    if (arcCardType) {
      arcCardType.textContent = `${arc.relationship_label}`;
      arcCardType.style.borderColor = arc.color;
      arcCardType.style.color = arc.color;
    }
    if (arcCardDistance) {
      arcCardDistance.textContent = `${arc.distance_books} books span (${arc.is_ot_to_nt ? 'OT ➔ NT' : 'Canonical'})`;
    }
    if (arcCardSource) arcCardSource.textContent = arc.source_ref;
    if (arcCardTarget) arcCardTarget.textContent = arc.target_ref;
    if (arcCardNotes) arcCardNotes.textContent = arc.notes || "Canonical Scripture relationship connecting prophecy/type to apostolic fulfillment.";

    if (arcActiveDetailCard) arcActiveDetailCard.classList.remove("hidden");
  }

  function renderArcSidebarList(arcs) {
    if (!arcSidebarList) return;
    arcSidebarList.innerHTML = "";
    if (arcs.length === 0) {
      arcSidebarList.innerHTML = `<div style="font-size: 11.5px; color: var(--text-muted); padding: 8px;">No matching arcs found.</div>`;
      return;
    }

    arcs.forEach((arc) => {
      const item = document.createElement("div");
      item.className = "arc-sidebar-item";
      item.setAttribute("data-id", arc.id);
      item.innerHTML = `
        <div class="arc-sb-top">
          <span class="arc-sb-src">${escapeHtml(arc.source_ref)}</span>
          <span style="color: var(--gold-primary);">➔</span>
          <span class="arc-sb-tgt">${escapeHtml(arc.target_ref)}</span>
        </div>
        <div class="arc-sb-type" style="color: ${arc.color};">${escapeHtml(arc.relationship_label)} (${arc.distance_books} bks)</div>
      `;
      item.addEventListener("click", () => {
        inspectArc(arc);
        highlightSidebarArc(arc.id);

        const svgPath = arcSvgViewport.querySelector(`.arc-path[data-id="${arc.id}"]`);
        if (svgPath) {
          arcSvgViewport.querySelectorAll(".arc-path").forEach((p) => {
            p.style.strokeWidth = "";
            p.style.strokeOpacity = "";
          });
          svgPath.style.strokeWidth = "4px";
          svgPath.style.strokeOpacity = "1";
        }
      });
      arcSidebarList.appendChild(item);
    });
  }

  function highlightSidebarArc(arcId) {
    if (!arcSidebarList) return;
    arcSidebarList.querySelectorAll(".arc-sidebar-item").forEach((it) => {
      if (parseInt(it.getAttribute("data-id"), 10) === arcId) {
        it.classList.add("selected");
        it.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else {
        it.classList.remove("selected");
      }
    });
  }

  if (selectArcType) selectArcType.addEventListener("change", loadArcNetwork);
  if (selectArcBook) selectArcBook.addEventListener("change", loadArcNetwork);
  if (selectArcScope) selectArcScope.addEventListener("change", loadArcNetwork);

  if (btnStageDownloadSvg) {
    btnStageDownloadSvg.addEventListener("click", () => {
      const relType = selectArcType ? selectArcType.value : "";
      const book = selectArcBook ? selectArcBook.value : "";
      const scope = selectArcScope ? selectArcScope.value : "OT-NT";
      const theme = getActiveThemeName();

      const params = new URLSearchParams();
      if (relType) params.append("type", relType);
      if (book) params.append("book", book);
      if (scope) params.append("testament", scope);
      params.append("theme", theme);
      params.append("width", "1600");
      params.append("height", "700");

      const link = document.createElement("a");
      link.href = `/api/crossref/arcs.svg?${params.toString()}`;
      link.download = "bible_typological_arcs.svg";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      showToast("Downloading high-resolution vector SVG...");
    });
  }

  if (btnReadArcPassage) {
    btnReadArcPassage.addEventListener("click", () => {
      if (!arcNetworkData || !activeArcId) return;
      const arc = (arcNetworkData.arcs || []).find((a) => a.id === activeArcId);
      if (arc) {
        const passageTab = document.querySelector('.nav-tab[data-view="passage"]');
        if (passageTab) passageTab.click();
        inputRef.value = arc.target_ref;
        fetchPassage(arc.target_ref);
        showToast(`Loaded ${arc.target_ref}`);
      }
    });
  }

  // -------------------------------------------------------------------------
  // Keyboard Shortcuts Subsystem
  // -------------------------------------------------------------------------
  btnShortcuts.addEventListener("click", () => {
    shortcutsModal.classList.remove("hidden");
  });

  btnCloseModal.addEventListener("click", () => {
    shortcutsModal.classList.add("hidden");
  });

  shortcutsModal.addEventListener("click", (e) => {
    if (e.target === shortcutsModal) {
      shortcutsModal.classList.add("hidden");
    }
  });

  window.addEventListener("keydown", (e) => {
    // If inside an input or select, only handle Escape
    const isEditing = ["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName);
    if (e.key === "Escape") {
      shortcutsModal.classList.add("hidden");
      if (isEditing) e.target.blur();
      return;
    }

    if (isEditing) return;

    if (e.key === "/" || e.key === "s") {
      e.preventDefault();
      headerQuickInput.focus();
    } else if (e.key === "[") {
      e.preventDefault();
      toggleSidebar();
    } else if (e.key === "f") {
      e.preventDefault();
      toggleFlowMode();
    } else if (e.key === "+" || e.key === "=") {
      e.preventDefault();
      btnFontInc.click();
    } else if (e.key === "-" || e.key === "_") {
      e.preventDefault();
      btnFontDec.click();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      btnPrevChapter.click();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      btnNextChapter.click();
    } else if (e.key === "t") {
      e.preventDefault();
      cycleTheme();
    } else if (e.key === "c") {
      e.preventDefault();
      copyCurrentPassage();
    } else if (e.key === "?") {
      e.preventDefault();
      shortcutsModal.classList.toggle("hidden");
    }
  });

  // -------------------------------------------------------------------------
  // Toast Helper
  // -------------------------------------------------------------------------
  let toastTimer = null;
  function showToast(msg, duration = 2200) {
    if (toastTimer) clearTimeout(toastTimer);
    toast.textContent = msg;
    toast.classList.remove("hidden");
    toastTimer = setTimeout(() => {
      toast.classList.add("hidden");
    }, duration);
  }

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
  loadRibbonDensity();
  fetchPassage("Romans 8:28-39", "WEB");
});

