/*  cca8_demo.ts
    CCA8 Intro Screens Demo (TypeScript / Node.js) 

    Save as:   cca8_demo.ts
    Compile:   tsc cca8_demo.ts
    Run:       node cca8_demo.js

    Notes:
      - This is intentionally a "large but simple" CLI demo: mostly text + a menu.
      - No external npm packages required.
      - We declare minimal Node globals so TypeScript can compile even without @types/node.
*/
var fs = require("fs");
var readline = require("readline");
var DEMO_VERSION = "0.1.0";
var CCA8_RUNNER_VERSION = "0.8.2"; // from cca8_run.py __version__
// ------------------------------ Small string helpers ------------------------------
function trimStr(s) {
    return (s || "").replace(/^\s+|\s+$/g, "");
}
function lower(s) {
    return (s || "").toLowerCase();
}
function isEmpty(s) {
    return trimStr(s) === "";
}
function padLeft(s, width, ch) {
    var ss = String(s);
    if (ss.length >= width)
        return ss;
    var out = "";
    for (var i = 0; i < width - ss.length; i++)
        out += ch;
    return out + ss;
}
function repeatChar(ch, n) {
    var out = "";
    for (var i = 0; i < n; i++)
        out += ch;
    return out;
}
function startsWith(s, pref) {
    var a = String(s);
    var p = String(pref);
    return a.substring(0, p.length) === p;
}
// ------------------------------ ANSI color helpers ------------------------------
function envHas(name) {
    try {
        return !!(process && process.env && process.env[name]);
    }
    catch (_e) {
        return false;
    }
}
function envGet(name, fallback) {
    try {
        var v = process && process.env ? process.env[name] : undefined;
        return v ? String(v) : fallback;
    }
    catch (_e) {
        return fallback;
    }
}
function shouldUseColor(noColorFlag) {
    if (noColorFlag)
        return false;
    if (envHas("NO_COLOR"))
        return false;
    try {
        return !!(process && process.stdout && process.stdout.isTTY);
    }
    catch (_e) {
        return false;
    }
}
function paint(text, code, enabled) {
    if (!enabled)
        return text;
    return "\x1b[" + code + "m" + text + "\x1b[0m";
}
// ------------------------------ Text payloads (intro screens) ------------------------------
var ASCII_BADGE = [
    "+--------------------------------------------------------------+",
    "|  C C A 8  —  Causal Cognitive Architecture                   |",
    "+--------------------------------------------------------------+",
].join("\n");
var ASCII_GOAT = [
    "    ____            CCA8",
    " .'    `-.       mountain goat",
    "/  _  _   \\",
    "| (o)(o)  |",
    "\\    __  /",
    " `'-.____'",
].join("\n");
// Key ideas (docstring section)
var KEY_IDEAS = [
    "Key ideas for readers and new collaborators",
    "------------------------------------------",
    "- Predicate: a symbolic fact token (e.g., \"posture:standing\").",
    "- Binding: a node instance carrying a predicate tag (pred:<token>) plus meta/engrams.",
    "- Edge: a directed link between bindings with a label (often \"then\") for weak causality.",
    "- WorldGraph: the small, fast episode index (~5% information). Rich content goes in engrams.",
    "- Policy (primitive): behavior object with trigger(world, drives) and execute(world, ctx, drives).",
    "  The Action Center scans the ordered list of policies and runs the first that triggers (one controller step).",
    "- Autosave/Load: JSON snapshot with world, drives, skills, plus a saved_at timestamp.",
].join("\n");
// Understanding bindings / tagging / policies (abridged but still large)
var UNDERSTANDING = [
    "",
    "==================== Understanding Bindings, Edges, Predicates, Cues & Policies ====================",
    "",
    "What is a Binding?",
    "  • A small 'episode card' that binds together:",
    "      - tags (symbols: predicates / actions / cues / anchors)",
    "      - engrams (pointers to rich memory outside WorldGraph)",
    "      - meta (provenance, timestamps, light notes)",
    "      - edges (directed links from this binding)",
    "",
    "  Structure (conceptual):",
    "      { id:'bN', tags:[...], engrams:{...}, meta:{...}, edges:[{'to':'bK','label':'then','meta':{...}}, ...] }",
    "",
    "Tag Families (use these prefixes)",
    "  • pred:*        → predicates (facts / goals you might plan TO)",
    "      examples: pred:posture:standing, pred:posture:fallen, pred:nipple:latched, pred:milk:drinking,",
    "                pred:proximity:mom:close, pred:proximity:shelter:near, pred:hazard:cliff:near",
    "",
    "  • action:*      → actions (verbs; what the agent did or is doing)",
    "      examples: action:push_up, action:extend_legs, action:orient_to_mom",
    "",
    "  • cue:*         → evidence/context you NOTICE (policy triggers); not planner goals",
    "      examples: cue:vision:silhouette:mom, cue:scent:milk, cue:sound:bleat:mom, cue:terrain:rocky",
    "                cue:drive:hunger_high, cue:drive:fatigue_high",
    "",
    "  • anchor:*      → orientation markers (e.g., anchor:NOW); also mapped in engine anchors {'NOW':'b1'}",
    "",
    "Drive thresholds (house style)",
    "  • Canonical storage: numeric values live in the Drives object:",
    "        drives.hunger, drives.fatigue, drives.warmth",
    "  • Threshold flags are derived (e.g., hunger>=HUNGER_HIGH) and are optionally emitted as rising-edge cues:",
    "        cue:drive:hunger_high, cue:drive:fatigue_high",
    "  • Only use pred:drive:* when you deliberately want a planner goal like pred:drive:warm_enough.",
    "    Otherwise treat thresholds as evidence (cue:drive:*).",
    "",
    "Edges = Transitions",
    "  • We treat edge labels as weak episode links (often just 'then').",
    "  • Most semantics live in bindings (pred:* and action:*); edge labels are for readability and metrics.",
    "  • Quantities about the transition live in edge.meta (e.g., meters, duration_s, created_by).",
    "  • Planner behavior today: BFS/Dijkstra follow structure (node/edge graph), not label meaning.",
    "",
    "Provenance & Engrams",
    "  • Who created a binding?   binding.meta['policy']='policy:<name>' (or meta.created_by for non-policy writes)",
    "  • Who created an edge?     edge.meta['created_by']='policy:<name>' (or similar)",
    "  • Where is the rich data?  binding.engrams[...] → pointers (large payloads live outside WorldGraph)",
    "",
    "Maps & Memory (where things live)",
    "  • WorldGraph  → symbolic episode index (bindings/edges/tags); great for inspection + planning over pred:*.",
    "  • BodyMap     → agent-centric working state used for gating (fast, “what do I believe right now?”).",
    "  • Drives      → numeric interoception state (hunger/fatigue/etc.); may emit cue:drive:* threshold events.",
    "  • Engrams     → pointers from bindings to richer payloads stored outside the graph (future: Column / disk store).",
    "",
    "Do / Don’t (project house style)",
    "  ✓ Use pred:* for facts/goals/events",
    "  ✓ Use action:* for verbs (what the agent does)",
    "  ✓ Use cue:* for evidence/conditions/triggers (including cue:drive:* threshold events)",
    "  ✓ Put creator/time/notes in meta; put action measurements in edge.meta",
    "  ✓ Allow anchor-only bindings (e.g., anchor:NOW)",
    "  ✗ Don’t store large data in tags; put it in engrams",
    "",
    "Examples",
    "  pred:posture:fallen --then--> action:push_up --then--> action:extend_legs --then--> pred:posture:standing",
    "  pred:posture:standing --then--> action:orient_to_mom --then--> pred:seeking_mom --then--> pred:nipple:latched",
    "",
    "(See README.md → Tagging Standard for more information.)",
    "",
].join("\n");
// Quick Tour (verbatim structure from the runner’s tour header)
var QUICK_TOUR = [
    "   === CCA8 Quick Tour ===",
    "",
    "Note:   Pending more tutorial-like upgrade.",
    "        Currently this 'tour' really just runs some of the menu routines without much explanation.",
    "        New version to be more interactive and provide better explanations.",
    "",
    "",
    "This tour will do the following and show the following displays:",
    "               (1) snapshot, (2) temporal context probe, (3) capture a small",
    "               engram, (4) show the binding pointer (b#), (5) inspect that",
    "               engram, (6) list/search engrams.",
    "Hints: Press Enter to accept defaults. Type Q to exit.",
    "",
    "**The tutorial portion of the tour is still under construction. All components shown here are available",
    "    as individual menu selections also -- see those and the README.md file for more details.**",
    "",
    "[tour] 1/6 — Baseline snapshot",
    "Shows CTX and TEMPORAL (dim/sigma/jump; cosine; hash). Next: temporal probe.",
    "  • CTX shows agent counters (profile, age_days, ticks) and run context.",
    "  • TEMPORAL is a soft clock (dim/sigma/jump), not wall time.",
    "  • cosine≈1.000 → same event; <0.90 → “new event soon.”",
    "  • vhash64 is a compact fingerprint for quick comparisons.",
    "",
    "[tour] 2/6 — Temporal context probe",
    "Updates the soft clock; prints dim/sigma/jump and cosine to last boundary.",
    "Next: capture a tiny engram.",
    "  • boundary() jumps the vector and increments the epoch (event count).",
    "  • vhash64 vs last_boundary_vhash64 → Hamming bits changed (0..64).",
    "  • Cosine compares “now” vs last boundary; drift lowers cosine.",
    "  • Status line summarizes phase (ON-BOUNDARY / DRIFTING / BOUNDARY-SOON).",
    "",
    "[tour] 3/6 — Capture a tiny engram",
    "Adds a memory item with time/provenance; visible in Snapshot. Next: show b#.",
    "  • capture_scene creates a binding (cue/pred) and a Column engram.",
    "  • The binding gets a pointer slot (e.g., column01 → EID).",
    "  • Time attrs (ticks, epoch, tvec64) come from ctx at capture time.",
    "  • binding.meta['policy'] records provenance when created by a policy.",
    "",
    "[tour] 4/6 — Show binding pointer (b#)",
    "Displays the new binding id and its attach target. Next: inspect that engram.",
    "  • A binding is the symbolic “memory link”; engram is the rich payload.",
    "  • The pointer (b#.engrams['slot']=EID) glues symbol ↔ rich memory.",
    "  • Attaching near NOW/LATEST keeps episodes readable for planning.",
    "  • Follow the pointer via Snapshot or “Inspect engram by id.”",
    "",
    "[tour] 5/6 — Inspect engram",
    "Shows engram fields (channel, token, attrs). Next: list/search engrams.",
    "  • meta → attrs (ticks, epoch, tvec64, epoch_vhash64) for time context.",
    "  • payload → kind/shape/bytes (varies by Column implementation).",
    "  • Use this to verify data shape and provenance after capture.",
    "  • Engrams persist across saves; pointers can be re-attached later.",
    "",
    "[tour] 6/6 — List/search engrams",
    "Lists and filters engrams by token/family.",
    "  • Deduped EIDs with source binding (b#) for quick auditing.",
    "  • Search by name substring and/or by epoch number.",
    "  • Useful to confirm capture cadence across boundaries/epochs.",
    "  • Pair with “Plan from NOW” to see if memory supports behavior.",
    "",
].join("\n");
var PROFILE_NARRATIVE_CHIMP = [
    "",
    "Chimpanzee-like brain simulation",
    "",
    "As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.",
    "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these",
    "    \"similar\" structures) but enhanced feedback pathways allowing better causal reasoning. Also better",
    "    combinatorial language.",
    "",
].join("\n");
var PROFILE_NARRATIVE_HUMAN = [
    "",
    "Human-like brain simulation",
    "",
    "As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.",
    "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these",
    "    \"similar\" structures) but enhanced feedback pathways allowing better causal reasoning. Also better",
    "    combinatorial language.",
    "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning",
    "    and compositional reasoning/language.",
    "",
].join("\n");
var PROFILE_NARRATIVE_MULTI_BRAINS = [
    "",
    "Human-like one-agent multiple-brains simulation",
    "",
    "As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.",
    "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these",
    "    \"similar\" structures) but enhanced feedback pathways allowing better causal reasoning. Also better",
    "    combinatorial language.",
    "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning",
    "    and compositional reasoning/language.",
    "",
    "In this model each agent has multiple brains operating in parallel. There is an intelligent voting mechanism to",
    "    decide on a response whereby each of the 5 processes running in parallel can give a response with an indication",
    "    of how certain they are this is the best response, and the most certain + most popular response is chosen.",
    "As well, all 5 symbolic maps along with their rich store of information in their engrams are continually learning",
    "    and constantly updated.",
    "",
].join("\n");
var PROFILE_NARRATIVE_SOCIETY = [
    "",
    "Human-like one-brain simulation × multiple-agents society",
    "",
    "As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.",
    "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these",
    "    \"similar\" structures) but enhanced feedback pathways allowing better causal reasoning. Also better",
    "    combinatorial language.",
    "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning",
    "    and compositional reasoning/language.",
    "",
    "In this simulation we have multiple agents each with one human-like brain, all interacting with each other.",
    "",
].join("\n");
var PROFILE_NARRATIVE_ADV_PLANNING = [
    "",
    "Human-like one-agent multiple-brains simulation with combinatorial planning",
    "",
    "As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.",
    "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these",
    "\"similar\" structures) but enhanced feedback pathways allowing better causal reasoning. Also better",
    "combinatorial language.",
    "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning",
    "and compositional reasoning/language.",
    "",
    "In this model there are multiple brains, e.g., 5 at the time of this writing, in one agent.",
    "There is an intelligent voting mechanism to decide on a response whereby each of the 5 processes running in",
    "parallel can give a response with an indication of how certain they are this is the best response, and the most",
    "certain + most popular response is chosen. As well, all 5 symbolic maps along with their rich store of",
    "information in their engrams are continually learning and updated.",
    "",
    "In addition, in this model each brain has multiple von Neumann processors to independently explore different",
    "possible routes to take or different possible decisions to make.",
    "",
].join("\n");
var PROFILE_NARRATIVE_SUPER = [
    "",
    "Super-human-like machine simulation",
    "",
    "Features scaffolding for an ASI-grade architecture:",
    "  • Hierarchical memory: massive multi-modal engrams (vision/sound/touch/text) linked to a compact symbolic index.",
    "  • Weighted graph planning: edges carry costs/uncertainty; A*/landmarks for long-range navigation in concept space.",
    "  • Meta-controller: blends proposals from symbolic search, neural value estimation, and program-synthesis planning.",
    "  • Self-healing & explanation: detect/repair inconsistent states; produce human-readable rationales for actions.",
    "  • Tool-use & embodiment: external tools (math/vision/robots) wrapped as policies with provenances and safeguards.",
    "  • Safety envelope: constraint-checking policies that can veto/redirect unsafe plans.",
    "",
    "This stub prints a dry-run of the meta-controller triage and falls back to the current==Mountain Goat profile.",
    "",
].join("\n");
var PROFILE_FALLBACK = [
    "Although scaffolding is in place, currently this evolutionary-like configuration is not available.",
    "Profile will be set to mountain goat-like brain simulation.",
    "",
].join("\n");
// ------------------------------ CLI + logging ------------------------------
var Logger = /** @class */ (function () {
    function Logger(path) {
        this.logStream = null;
        if (path && !isEmpty(path)) {
            try {
                this.logStream = fs.createWriteStream(path, { flags: "a" });
            }
            catch (_e) {
                this.logStream = null;
            }
        }
    }
    Logger.prototype.close = function () {
        try {
            if (this.logStream)
                this.logStream.end();
        }
        catch (_e) {
            // ignore
        }
        this.logStream = null;
    };
    Logger.prototype.write = function (text) {
        // Console
        try {
            process.stdout.write(text);
        }
        catch (_e) {
            // fallback
            try {
                console.log(text);
            }
            catch (_e2) { /* ignore */ }
        }
        // File transcript
        try {
            if (this.logStream)
                this.logStream.write(text);
        }
        catch (_e) {
            // ignore
        }
    };
    Logger.prototype.line = function (text) {
        this.write(text + "\n");
    };
    Logger.prototype.block = function (text) {
        // Preserve the text as-is (and ensure it ends with newline)
        this.write(text);
        if (!endsWithNewline(text))
            this.write("\n");
    };
    return Logger;
}());
function endsWithNewline(s) {
    if (!s)
        return false;
    var last = s.substring(s.length - 1);
    return last === "\n";
}
var Cli = /** @class */ (function () {
    function Cli(logger) {
        this.logger = logger;
        this.rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    }
    Cli.prototype.close = function () {
        try {
            this.rl.close();
        }
        catch (_e) { /* ignore */ }
        this.logger.close();
    };
    Cli.prototype.out = function (line) {
        this.logger.line(line);
    };
    Cli.prototype.outBlock = function (text) {
        this.logger.block(text);
    };
    Cli.prototype.prompt = function (question, cb) {
        this.rl.question(question, function (answer) {
            cb(String(answer));
        });
    };
    Cli.prototype.pause = function (cb) {
        this.prompt("\nPress Enter to continue (or type Q to quit): ", cb);
    };
    return Cli;
}());
// ------------------------------ Arg parsing ------------------------------
function defaultOptions() {
    return {
        about: false,
        version: false,
        understanding: false,
        tour: false,
        noIntro: false,
        noColor: false,
        logo: null,
        profile: null,
        logPath: null,
    };
}
function parseArgs(argv) {
    var opts = defaultOptions();
    var i = 0;
    while (i < argv.length) {
        var a = String(argv[i]);
        if (a === "--version") {
            opts.version = true;
            i += 1;
            continue;
        }
        if (a === "--about") {
            opts.about = true;
            i += 1;
            continue;
        }
        if (a === "--understanding") {
            opts.understanding = true;
            i += 1;
            continue;
        }
        if (a === "--tour") {
            opts.tour = true;
            i += 1;
            continue;
        }
        if (a === "--no-intro") {
            opts.noIntro = true;
            i += 1;
            continue;
        }
        if (a === "--no-color") {
            opts.noColor = true;
            i += 1;
            continue;
        }
        if (a === "--logo") {
            var v = (i + 1 < argv.length) ? String(argv[i + 1]) : "";
            var vv = lower(trimStr(v));
            if (vv === "badge" || vv === "goat" || vv === "off") {
                opts.logo = vv;
                i += 2;
                continue;
            }
            i += 1;
            continue;
        }
        if (a === "--profile") {
            var v2 = (i + 1 < argv.length) ? String(argv[i + 1]) : "";
            if (!isEmpty(v2)) {
                opts.profile = trimStr(v2);
                i += 2;
                continue;
            }
            i += 1;
            continue;
        }
        if (a === "--log") {
            var lp = (i + 1 < argv.length) ? String(argv[i + 1]) : "";
            if (!isEmpty(lp)) {
                opts.logPath = trimStr(lp);
                i += 2;
                continue;
            }
            i += 1;
            continue;
        }
        if (a === "--help" || a === "-h") {
            // Treat as about-ish
            opts.about = true;
            i += 1;
            continue;
        }
        // Unknown flag: ignore
        i += 1;
    }
    return opts;
}
// ------------------------------ Renderers (banner, about, etc.) ------------------------------
function logoFromEnvOrDefault(explicit) {
    if (explicit)
        return explicit;
    var v = lower(trimStr(envGet("CCA8_LOGO", "badge")));
    if (v === "badge" || v === "goat" || v === "off")
        return v;
    return "badge";
}
function printAsciiLogo(cli, style, colorEnabled) {
    if (style === "off")
        return;
    var art = (style === "goat") ? ASCII_GOAT : ASCII_BADGE;
    if (colorEnabled) {
        if (style === "badge") {
            art = art.replace("C C A 8", paint("C C A 8", "1;36", true));
        }
        else if (style === "goat") {
            art = paint(art, "33", true);
        }
    }
    cli.outBlock(art + "\n");
}
function printHeader(cli, st) {
    cli.out("");
    cli.out("");
    cli.out("# " + repeatChar("-", 86));
    cli.out("# NEW RUN   NEW RUN");
    cli.out("# " + repeatChar("-", 86));
    cli.out("");
    cli.out("A Warm Welcome to the CCA8 Mammalian Brain Simulation");
    cli.out("(cca8_run.py v" + CCA8_RUNNER_VERSION + " | cca8_demo.ts v" + DEMO_VERSION + ")");
    cli.out("");
    // Header prints the goat logo (mirrors print_header(style="goat"))
    printAsciiLogo(cli, "goat", st.colorEnabled);
    var entry = getEntrypoint();
    var osName = getOsLabel();
    cli.out("Entry point program being run: " + entry);
    cli.out("OS: " + osName + " (see system-dependent utilities for more detailed system/simulation info)");
    cli.out("(for non-interactive execution, run with --help to see optional flags you can set)");
    cli.out("");
    cli.out("Embodiment:  HAL (hardware abstraction layer) setting: " + st.halStatus);
    cli.out("Embodiment:  body_type|version_number|serial_number (i.e. robotic embodiment): " + st.bodyStatus);
    cli.out("");
    cli.out("The simulation of the cognitive architecture can be adjusted to add or take away");
    cli.out("  various features, allowing exploration of different evolutionary-like configurations.");
    cli.out("");
    cli.out("  1. Mountain Goat-like brain simulation");
    cli.out("  2. Chimpanzee-like brain simulation");
    cli.out("  3. Human-like brain simulation");
    cli.out("  4. Human-like one-agent multiple-brains simulation");
    cli.out("  5. Human-like one-brain simulation × multiple-agents society");
    cli.out("  6. Human-like one-agent multiple-brains simulation with combinatorial planning");
    cli.out("  7. Super-Human-like machine simulation");
    cli.out("  T. Tutorial (more information) on using and maintaining this program, references");
    cli.out("");
}
function getEntrypoint() {
    try {
        var p = process && process.argv && process.argv.length >= 2 ? String(process.argv[1]) : "(unknown)";
        return p;
    }
    catch (_e) {
        return "(unknown)";
    }
}
function getOsLabel() {
    try {
        return String(process.platform);
    }
    catch (_e) {
        return "(unknown)";
    }
}
function printAbout(cli) {
    cli.out("");
    cli.out("CCA8 Demo — About");
    cli.out(repeatChar("-", 78));
    cli.out("");
    cli.outBlock(KEY_IDEAS + "\n");
    cli.out("");
    cli.out("This demo program is a text-only CLI wrapper around the intro/help text.");
    cli.out("It does NOT run the CCA8 simulation itself; it only teaches what the terms mean.");
    cli.out("");
    cli.out("Try: --understanding  |  --tour  |  --about  |  --version  |  --no-intro");
    cli.out("");
}
function printVersion(cli) {
    cli.out("cca8_demo.ts v" + DEMO_VERSION);
    cli.out("based on cca8_run.py v" + CCA8_RUNNER_VERSION);
}
function printUnderstanding(cli) {
    cli.outBlock(UNDERSTANDING);
}
function printQuickTour(cli) {
    cli.outBlock(QUICK_TOUR);
}
function printTutorialMenu(cli) {
    cli.out("");
    cli.out("Tutorial options:");
    cli.out("  1) README/compendium System Documentation");
    cli.out("  2) Console Tour (pending)  (use menu item 'Quick Tour' here)");
    cli.out("  [Enter] Cancel");
    cli.out("");
}
function showReadmeHint(cli) {
    // In Python runner, 'T' opens README.md. Here we just print the expected path.
    cli.out("");
    cli.out("[tutorial] README.md is the compendium document in the CCA8 project folder.");
    cli.out("[tutorial] Open it in your editor (or the repo viewer) for deeper details and references.");
    cli.out("");
}
// ------------------------------ Profile selection ------------------------------
function normalizeProfileInput(s) {
    var x = lower(trimStr(s));
    // numeric shortcuts
    if (x === "1")
        return "goat";
    if (x === "2")
        return "chimp";
    if (x === "3")
        return "human";
    if (x === "4")
        return "multi";
    if (x === "5")
        return "society";
    if (x === "6")
        return "planning";
    if (x === "7")
        return "super";
    // name shortcuts
    if (x === "goat" || x === "mountain_goat" || x === "mountaingoat")
        return "goat";
    if (x === "chimp" || x === "chimpanzee")
        return "chimp";
    if (x === "human")
        return "human";
    if (x === "multi" || x === "multi_brain" || x === "multibrains" || x === "multiple_brains")
        return "multi";
    if (x === "society" || x === "agents" || x === "multi_agents" || x === "multiagent")
        return "society";
    if (x === "planning" || x === "adv" || x === "combinatorial")
        return "planning";
    if (x === "super" || x === "asi" || x === "superhuman")
        return "super";
    return x;
}
function profileNarrative(kind) {
    if (kind === "chimp")
        return PROFILE_NARRATIVE_CHIMP + PROFILE_FALLBACK;
    if (kind === "human")
        return PROFILE_NARRATIVE_HUMAN + PROFILE_FALLBACK;
    if (kind === "multi")
        return PROFILE_NARRATIVE_MULTI_BRAINS + PROFILE_FALLBACK;
    if (kind === "society")
        return PROFILE_NARRATIVE_SOCIETY + PROFILE_FALLBACK;
    if (kind === "planning")
        return PROFILE_NARRATIVE_ADV_PLANNING + PROFILE_FALLBACK;
    if (kind === "super")
        return PROFILE_NARRATIVE_SUPER + PROFILE_FALLBACK;
    return "";
}
function promptForProfile(cli, st, preselected, cb) {
    // If preselected, apply it without prompting (but still show narrative if it’s not goat).
    if (preselected && !isEmpty(preselected)) {
        var kind = normalizeProfileInput(preselected);
        if (kind !== "goat" && kind !== "t") {
            var txt = profileNarrative(kind);
            if (!isEmpty(txt))
                cli.outBlock(txt);
        }
        st.profileName = "Mountain Goat";
        cb(st.profileName);
        return;
    }
    var promptText = "Please make a choice [1–7 or T | Enter = Mountain Goat]: ";
    cli.prompt(promptText, function (answer) {
        var raw = trimStr(answer);
        if (raw === "") {
            st.profileName = "Mountain Goat";
            cb(st.profileName);
            return;
        }
        var a = lower(raw);
        if (a === "t") {
            printTutorialMenu(cli);
            cli.prompt("Choose: ", function (pick) {
                var p = trimStr(pick);
                if (p === "1") {
                    showReadmeHint(cli);
                }
                else if (p === "2") {
                    cli.out("Console tour is pending; please use the Quick Tour menu item (or README) for now.");
                    cli.out("");
                }
                else {
                    cli.out("(cancelled)");
                    cli.out("");
                }
                // Re-prompt for profile after tutorial menu
                promptForProfile(cli, st, null, cb);
            });
            return;
        }
        var kind = normalizeProfileInput(raw);
        if (kind !== "goat") {
            var txt2 = profileNarrative(kind);
            if (!isEmpty(txt2))
                cli.outBlock(txt2);
        }
        // In the runner, all other profiles fall back to goat
        st.profileName = "Mountain Goat";
        cb(st.profileName);
    });
}
// ------------------------------ Main menu (simple but a bit “runner-like”) ------------------------------
var MENU_TEXT = [
    "",
    "[hints for text selection instead of numerical selection]",
    "",
    "# Quick Start & Tutorial",
    "1) Understanding bindings, edges, predicates, cues, policies [understanding, tagging]",
    "2) CCA8 Quick Tour (text-only) [help, tutorial, tour]",
    "",
    "# Quick Start / Overview",
    "3) About / Key ideas [about]",
    "4) Show intro header again [header]",
    "5) Choose profile again [profile]",
    "",
    "# Misc",
    "6) Show ASCII logo (badge/goat/off) [logo]",
    "7) Quit [quit, exit]",
    "",
    "Select: ",
].join("\n");
var MIN_PREFIX = 3;
var ALIASES = {
    // menu items
    "understanding": "1",
    "tagging": "1",
    "help": "2",
    "tutorial": "2",
    "tour": "2",
    "about": "3",
    "header": "4",
    "profile": "5",
    "logo": "6",
    "badge": "6",
    "goat": "6",
    "off": "6",
    "quit": "7",
    "exit": "7",
    "q": "7",
};
function routeAlias(cmd) {
    var s = lower(trimStr(cmd));
    if (Object.prototype.hasOwnProperty.call(ALIASES, s)) {
        return { routed: ALIASES[s], matches: [] };
    }
    if (s.length >= MIN_PREFIX) {
        var keys = Object.keys(ALIASES);
        var matches = [];
        for (var i = 0; i < keys.length; i++) {
            var k = keys[i];
            if (startsWith(k, s))
                matches.push(k);
        }
        if (matches.length === 1)
            return { routed: ALIASES[matches[0]], matches: matches };
        return { routed: null, matches: matches };
    }
    return { routed: null, matches: [] };
}
function menuLoop(cli, st) {
    cli.prompt(MENU_TEXT, function (rawAnswer) {
        var choice = trimStr(rawAnswer);
        var lowerChoice = lower(choice);
        if (!isEmpty(choice)) {
            if (!isDigits(choice)) {
                var routed = routeAlias(choice);
                if (routed.routed !== null) {
                    choice = routed.routed;
                }
                else if (routed.matches.length > 1) {
                    cli.out("[help] Ambiguous input '" + lowerChoice + "'. Try one of: " + routed.matches.slice(0, 8).join(", ") + (routed.matches.length > 8 ? "..." : ""));
                    menuLoop(cli, st);
                    return;
                }
            }
        }
        if (choice === "1") {
            printUnderstanding(cli);
            cli.pause(function (ans) {
                if (lower(trimStr(ans)) === "q") {
                    cli.out("Goodbye.");
                    cli.close();
                    return;
                }
                menuLoop(cli, st);
            });
            return;
        }
        if (choice === "2") {
            printQuickTour(cli);
            cli.pause(function (ans2) {
                if (lower(trimStr(ans2)) === "q") {
                    cli.out("Goodbye.");
                    cli.close();
                    return;
                }
                menuLoop(cli, st);
            });
            return;
        }
        if (choice === "3") {
            printAbout(cli);
            cli.pause(function (ans3) {
                if (lower(trimStr(ans3)) === "q") {
                    cli.out("Goodbye.");
                    cli.close();
                    return;
                }
                menuLoop(cli, st);
            });
            return;
        }
        if (choice === "4") {
            printHeader(cli, st);
            cli.pause(function (ans4) {
                if (lower(trimStr(ans4)) === "q") {
                    cli.out("Goodbye.");
                    cli.close();
                    return;
                }
                menuLoop(cli, st);
            });
            return;
        }
        if (choice === "5") {
            promptForProfile(cli, st, null, function (_profile) {
                cli.out("Profile set: " + st.profileName + " (scaffolding profiles fall back to goat for now).");
                cli.out("");
                menuLoop(cli, st);
            });
            return;
        }
        if (choice === "6") {
            // Let user pick a logo style for display only (badge/goat/off)
            cli.out("");
            cli.out("Logo options:");
            cli.out("  1) badge");
            cli.out("  2) goat");
            cli.out("  3) off");
            cli.out("");
            cli.prompt("Choose (default=badge): ", function (pick) {
                var p = lower(trimStr(pick));
                var style = "badge";
                if (p === "2" || p === "goat")
                    style = "goat";
                else if (p === "3" || p === "off")
                    style = "off";
                else
                    style = "badge";
                st.logoStyle = style;
                cli.out("");
                cli.out("[logo] style set to: " + style);
                cli.out("");
                printAsciiLogo(cli, style, st.colorEnabled);
                cli.pause(function (_ans5) {
                    menuLoop(cli, st);
                });
            });
            return;
        }
        if (choice === "7" || lowerChoice === "q") {
            cli.out("Goodbye.");
            cli.close();
            return;
        }
        // default: treat empty as "show menu again"
        menuLoop(cli, st);
    });
}
function isDigits(s) {
    var t = trimStr(s);
    if (t.length === 0)
        return false;
    for (var i = 0; i < t.length; i++) {
        var c = t.charCodeAt(i);
        if (c < 48 || c > 57)
            return false;
    }
    return true;
}
// ------------------------------ main() ------------------------------
function main() {
    var args = parseArgs(getArgv());
    var logger = new Logger(args.logPath);
    var cli = new Cli(logger);
    var state = {
        profileName: "Mountain Goat",
        halStatus: "HAL: off (no embodiment)",
        bodyStatus: "Body: (none)",
        logoStyle: logoFromEnvOrDefault(args.logo),
        colorEnabled: shouldUseColor(args.noColor),
    };
    // One-shot modes
    if (args.version) {
        printVersion(cli);
        cli.close();
        return;
    }
    if (args.about) {
        printAbout(cli);
        cli.close();
        return;
    }
    if (args.understanding) {
        printUnderstanding(cli);
        cli.close();
        return;
    }
    if (args.tour) {
        printQuickTour(cli);
        cli.close();
        return;
    }
    // Interactive mode
    if (!args.noIntro) {
        printHeader(cli, state);
    }
    else {
        // Still show the badge logo (respect env/flags)
        printAsciiLogo(cli, state.logoStyle, state.colorEnabled);
    }
    // Profile selection then menu loop
    promptForProfile(cli, state, args.profile, function (_profileName) {
        cli.out("Profile set: " + state.profileName + " (sigma/jump/winners_k omitted in this TS demo).");
        cli.out("");
        menuLoop(cli, state);
    });
}
function getArgv() {
    try {
        var out = [];
        var a = process && process.argv ? process.argv : [];
        for (var i = 2; i < a.length; i++)
            out.push(String(a[i]));
        return out;
    }
    catch (_e) {
        return [];
    }
}
main();
