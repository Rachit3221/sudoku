(function () {
  const boardEl = document.getElementById("board");
  const levelEl = document.getElementById("level");
  const newBtn = document.getElementById("new-game");
  const checkBtn = document.getElementById("check");
  const statusEl = document.getElementById("status");

  const API = (typeof window !== "undefined" && window.SUDOKU_API) ? window.SUDOKU_API : "/api/new_puzzle";

  let puzzle = null;
  let solution = null;
  let solved = false;

  function clampDigit(v){
    if(!v) return "";
    v = v.replace(/[^1-9]/g,"");
    if(v.length>1) v=v[0];
    return v;
  }

  async function loadPuzzle() {
    try {
      solved = false;
      const lvl = levelEl.value || "easy";
      statusEl.textContent = "Loading a new " + lvl + " puzzle…";
      const res = await fetch(API + "?level=" + encodeURIComponent(lvl), { credentials: "include" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      puzzle = data.puzzle;
      solution = data.solution;
      drawBoard();
      statusEl.textContent = "Fill the grid. Wrong inputs turn red — try again!";
    } catch (err) {
      console.error("Failed to load puzzle:", err);
      statusEl.textContent = "Could not load puzzle. Please click 'New Game' again.";
    }
  }

  function drawBoard() {
    boardEl.innerHTML = "";
    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < 9; c++) {
        const v = puzzle[r][c];
        const cell = document.createElement("div");
        cell.className = "cell";
        if (r % 3 === 0) cell.style.borderTop = "2px solid var(--outline)";
        if (c % 3 === 0) cell.style.borderLeft = "2px solid var(--outline)";
        if (r === 8) cell.style.borderBottom = "2px solid var(--outline)";
        if (c === 8) cell.style.borderRight = "2px solid var(--outline)";

        const input = document.createElement("input");
        input.setAttribute("inputmode","numeric");
        input.setAttribute("maxlength","1");
        input.dataset.r = r; input.dataset.c = c;

        if (v !== 0) {
          input.value = v;
          input.disabled = true;
          cell.classList.add("prefilled");
        } else {
          input.addEventListener("input", onEditCell);
          input.addEventListener("focus", () => {
            statusEl.textContent = `Cell r${r+1}c${c+1}: enter 1–9.`;
          });
        }
        cell.appendChild(input);
        boardEl.appendChild(cell);
      }
    }
  }

  function onEditCell(e) {
    if (solved) return;
    const input = e.target;
    input.value = clampDigit(input.value);

    const r = parseInt(input.dataset.r, 10);
    const c = parseInt(input.dataset.c, 10);
    const val = input.value ? parseInt(input.value, 10) : 0;

    const cell = input.parentElement;
    cell.classList.remove("correct", "wrong");

    if (val === 0) {
      statusEl.textContent = "Cell cleared.";
      return;
    }
    if (!solution) return;
    if (solution[r][c] !== val) {
      cell.classList.add("wrong");
      input.setAttribute("aria-invalid", "true");
      statusEl.textContent = `❌ ${val} is incorrect at r${r+1}c${c+1}. Please try again.`;
    } else {
      cell.classList.add("correct");
      input.setAttribute("aria-invalid", "false");
      statusEl.textContent = `✅ Good! ${val} is correct at r${r+1}c${c+1}.`;
    }
  }

  function revealSolution() {
    if (!solution) return;
    const inputs = boardEl.querySelectorAll("input");
    let hadWrong = false;

    inputs.forEach(inp => {
      const r = parseInt(inp.dataset.r, 10);
      const c = parseInt(inp.dataset.c, 10);
      if (inp.disabled) return;
      const userVal = inp.value ? parseInt(inp.value, 10) : 0;
      const cell = inp.parentElement;
      cell.classList.remove("wrong", "correct");
      if (userVal !== solution[r][c]) {
        hadWrong = true;
        cell.classList.add("wrong");
      } else {
        cell.classList.add("correct");
      }
    });

    statusEl.textContent = hadWrong
      ? "Showing the correct solution. Your incorrect entries were highlighted."
      : "Great! Here is the completed solution.";

    setTimeout(() => {
      inputs.forEach(inp => {
        const r = parseInt(inp.dataset.r, 10);
        const c = parseInt(inp.dataset.c, 10);
        inp.value = solution[r][c];
        inp.disabled = true;
        const cell = inp.parentElement;
        cell.classList.remove("wrong");
        cell.classList.add("correct");
      });
      solved = true;
    }, 600);
  }

  newBtn.addEventListener("click", loadPuzzle);
  checkBtn.addEventListener("click", revealSolution);
  levelEl.addEventListener("change", loadPuzzle);

  // initial
  loadPuzzle();
})();
