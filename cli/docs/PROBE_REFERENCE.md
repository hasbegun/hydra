# Garak Probe Reference

Complete list of all probes available in garak v0.17.1. Use these names in
the `probes:` section of your YAML scan plan.

**Active** probes run by default when no probe list is specified.
**Extended** (`[extended]`) probes are slower / more exhaustive variants
that only run when explicitly listed.

---

## Choosing Probes by Time Budget

| Budget | Probes | Est. Prompts | Example |
|--------|--------|-------------|---------|
| ~5 min | `goodside.ThreatenJSON`, `goodside.WhoIsRiley`, `lmrc.Bullying` | ~14 | `examples/quick-ollama.yaml` |
| ~15 min | Above + `promptinject.HijackKillHumans`, `exploitation.SQLInjectionEcho` | ~30 | |
| ~30 min | `dan`, `promptinject` (modules) | ~50+ | |
| ~60 min | `dan`, `encoding`, `promptinject` (modules) | ~200+ | `examples/rest-test.yaml` |
| 2+ hrs | All active probes | 500+ | `preset: thorough` |

---

## Probe Categories

### goodside — Prompt Hijacking (3 active / 4 total)
Tests whether the model's output can be hijacked to produce attacker-controlled content.

| Probe | Prompts | Notes |
|-------|---------|-------|
| `goodside.Tag` | ? | Tag-based injection |
| `goodside.ThreatenJSON` | 1 | Hijack output to JSON format |
| `goodside.WhoIsRiley` | 6 | Identity confusion attack |
| `goodside.Davidjl` | 4 | `[extended]` |

### dan — Do Anything Now / Jailbreaks (3 active / 19 total)
Classic jailbreak prompts that attempt to bypass safety guidelines.

| Probe | Prompts | Notes |
|-------|---------|-------|
| `dan.Ablation_Dan_11_0` | ? | DAN 11.0 ablation study |
| `dan.AutoDANCached` | ? | Cached AutoDAN attacks |
| `dan.DanInTheWild` | ? | Real-world DAN prompts |
| `dan.AntiDAN` | ? | `[extended]` |
| `dan.AutoDAN` | ? | `[extended]` — generates attacks |
| `dan.ChatGPT_Developer_Mode_RANTI` | ? | `[extended]` |
| `dan.ChatGPT_Developer_Mode_v2` | ? | `[extended]` |
| `dan.ChatGPT_Image_Markdown` | ? | `[extended]` |
| `dan.DAN_Jailbreak` | ? | `[extended]` |
| `dan.DUDE` | ? | `[extended]` |
| `dan.DanInTheWildFull` | ? | `[extended]` — full variant |
| `dan.Dan_6_0` through `dan.Dan_11_0` | ? | `[extended]` — individual DAN versions |
| `dan.STAN` | ? | `[extended]` |

### encoding — Encoded Injection (15 active / 20 total)
Encodes malicious prompts in various formats to bypass input filters.

| Probe | Notes |
|-------|-------|
| `encoding.InjectAscii85` | ASCII85 encoded injection |
| `encoding.InjectAtbash` | Atbash cipher |
| `encoding.InjectBase16` | Base16 (hex) |
| `encoding.InjectBase2048` | Base2048 |
| `encoding.InjectBase32` | Base32 |
| `encoding.InjectBase64` | Base64 |
| `encoding.InjectBraille` | Braille encoding |
| `encoding.InjectEcoji` | Ecoji (emoji encoding) |
| `encoding.InjectHex` | Hexadecimal |
| `encoding.InjectMorse` | Morse code |
| `encoding.InjectNato` | NATO alphabet |
| `encoding.InjectROT13` | ROT13 cipher |
| `encoding.InjectUU` | UUencode |
| `encoding.InjectUnicodeTagChars` | Unicode tag characters |
| `encoding.InjectZalgo` | Zalgo text |
| `encoding.InjectLeet` | `[extended]` — Leet speak |
| `encoding.InjectMime` | `[extended]` — MIME encoding |
| `encoding.InjectQP` | `[extended]` — Quoted-printable |
| `encoding.InjectSneakyBits` | `[extended]` — Bit-level obfuscation |
| `encoding.InjectUnicodeVariantSelectors` | `[extended]` |

### promptinject — Prompt Injection (3 active / 6 total)
Direct prompt injection attacks that try to override system instructions.

| Probe | Notes |
|-------|-------|
| `promptinject.HijackHateHumans` | Inject "hate humans" output |
| `promptinject.HijackKillHumans` | Inject "kill humans" output |
| `promptinject.HijackLongPrompt` | Long-form injection |
| `promptinject.HijackHateHumansFull` | `[extended]` |
| `promptinject.HijackKillHumansFull` | `[extended]` |
| `promptinject.HijackLongPromptFull` | `[extended]` |

### exploitation — Code Injection (2 active / 3 total)
Tests for code injection vulnerabilities (SQL, Jinja template).

| Probe | Notes |
|-------|-------|
| `exploitation.JinjaTemplatePythonInjection` | Jinja2 SSTI |
| `exploitation.SQLInjectionEcho` | SQL injection via echo |
| `exploitation.SQLInjectionSystem` | `[extended]` |

### web_injection — Web Attack Vectors (8 active / 8 total)
Web-specific attacks: XSS, markdown exfiltration, data leakage.

| Probe | Notes |
|-------|-------|
| `web_injection.ColabAIDataLeakage` | Colab AI data leak |
| `web_injection.MarkdownImageExfil` | Markdown image exfiltration |
| `web_injection.MarkdownURIImageExfilExtended` | URI-based image exfil |
| `web_injection.MarkdownURINonImageExfilExtended` | URI non-image exfil |
| `web_injection.MarkdownXSS` | XSS via markdown |
| `web_injection.PlaygroundMarkdownExfil` | Playground markdown exfil |
| `web_injection.StringAssemblyDataExfil` | String assembly data exfil |
| `web_injection.TaskXSS` | Task-based XSS |

### latentinjection — Hidden Instruction Injection (9 active / 17 total)
Injects hidden instructions into documents, resumes, reports that the model processes.

| Probe | Notes |
|-------|-------|
| `latentinjection.LatentInjectionFactSnippetEiffel` | Fact snippet (Eiffel) |
| `latentinjection.LatentInjectionFactSnippetLegal` | Fact snippet (legal) |
| `latentinjection.LatentInjectionReport` | Report injection |
| `latentinjection.LatentInjectionResume` | Resume injection |
| `latentinjection.LatentInjectionTranslationEnFr` | Translation En→Fr |
| `latentinjection.LatentInjectionTranslationEnZh` | Translation En→Zh |
| `latentinjection.LatentJailbreak` | Latent jailbreak |
| `latentinjection.LatentWhois` | Whois injection |
| `latentinjection.LatentWhoisSnippet` | Whois snippet injection |
| *Full variants* | `[extended]` — 8 additional full variants |

### lmrc — Language Model Risk Cards (6 active / 8 total)
Content safety tests based on the LMRC framework.

| Probe | Prompts | Notes |
|-------|---------|-------|
| `lmrc.Bullying` | 7 | Bullying content |
| `lmrc.Deadnaming` | 6 | Deadnaming |
| `lmrc.QuackMedicine` | 1 | Medical misinformation |
| `lmrc.SexualContent` | 1 | Sexual content generation |
| `lmrc.Sexualisation` | 3 | Sexualisation |
| `lmrc.SlurUsage` | 1 | Slur generation |
| `lmrc.Anthropomorphisation` | 6 | `[extended]` |
| `lmrc.Profanity` | 2 | `[extended]` |

### sysprompt_extraction — System Prompt Leak (1 active / 1 total)
Attempts to extract the system prompt from the model.

| Probe | Notes |
|-------|-------|
| `sysprompt_extraction.SystemPromptExtraction` | Direct extraction attempts |

### apikey — API Key Leakage (2 active / 2 total)
Tests whether the model leaks API keys or credentials.

| Probe | Notes |
|-------|-------|
| `apikey.CompleteKey` | Complete a partial API key |
| `apikey.GetKey` | Ask for an API key directly |

### malwaregen — Malware Generation (4 active / 4 total)
Tests whether the model generates malicious code.

| Probe | Notes |
|-------|-------|
| `malwaregen.Evasion` | AV evasion techniques |
| `malwaregen.Payload` | Malware payloads |
| `malwaregen.SubFunctions` | Malware sub-functions |
| `malwaregen.TopLevel` | Top-level malware |

### packagehallucination — Package Hallucination (7 active / 7 total)
Tests if the model recommends non-existent packages (supply chain risk).

| Probe | Notes |
|-------|-------|
| `packagehallucination.Python` | Python packages |
| `packagehallucination.JavaScript` | npm packages |
| `packagehallucination.Ruby` | Ruby gems |
| `packagehallucination.Rust` | Rust crates |
| `packagehallucination.Dart` | Dart packages |
| `packagehallucination.Perl` | Perl modules |
| `packagehallucination.RakuLand` | Raku packages |

### Other Active Probes

| Category | Probe | Notes |
|----------|-------|-------|
| `adaptive_attacks` | `AdaptiveAttacks` | Adaptive attack generation |
| `ansiescape` | `AnsiEscaped`, `AnsiRaw` | ANSI escape sequence injection |
| `atkgen` | `Tox` | Toxic content generation |
| `badchars` | `BadCharacters` | Bad character handling |
| `continuation` | `ContinueSlursReclaimedSlurs` | Slur continuation |
| `divergence` | `Repeat`, `RepeatedToken` | Divergence / memorization |
| `dra` | `DRA` | Direct request attack |
| `grandma` | `Slurs`, `Substances`, `Win10`, `Win11` | Social engineering |
| `leakreplay` | 8 active probes | Training data memorization |
| `misleading` | `FalseAssertion` | False assertion acceptance |
| `phrasing` | `FutureTense`, `PastTense` | Tense-based bypass |
| `realtoxicityprompts` | `RTPBlank` (5 prompts) | Toxicity prompts |
| `sata` | `MLM` | MLM scheme detection |
| `snowball` | `GraphConnectivity` | Logical reasoning attacks |
| `suffix` | `GCGCached` (26 prompts) | Adversarial suffix attacks |
| `tap` | `TAPCached` | Tree of Attacks with Pruning |
| `topic` | `WordnetControversial` | Controversial topic generation |

### Extended-Only Categories

These categories have **no active probes** — all must be explicitly listed:

| Category | Probes | Notes |
|----------|--------|-------|
| `agent_breaker` | `AgentBreaker` | Agent tool-use attacks |
| `audio` | `AudioAchillesHeel` | Audio-based attacks |
| `av_spam_scanning` | `EICAR`, `GTUBE`, `GTphish` | AV/spam test patterns |
| `doctor` | `Bypass`, `BypassLeet`, `Puppetry` | Doctor role-play bypass |
| `donotanswer` | 5 probes | Do-not-answer safety tests |
| `fileformats` | `HF_Files` | File format attacks |
| `fitd` | `FITD` | Foot-in-the-door technique |
| `glitch` | `Glitch`, `GlitchFull` | Glitch token attacks |
| `goat` | `GOATAttack` | GOAT adversarial attacks |
| `propile` | 4 PII leak probes | PII extraction |
| `smuggling` | 3 probes | Prompt smuggling |
| `test` | `Blank`, `Test` | Test / debug probes |
| `visual_jailbreak` | `FigStep`, `FigStepFull` | Visual jailbreak (requires image) |

---

## Recommended Scan Plans

### Smoke Test (~5 min) — `examples/quick-ollama.yaml`
```yaml
probes:
  - goodside.ThreatenJSON       # 1 prompt
  - goodside.WhoIsRiley         # 6 prompts
  - lmrc.Bullying               # 7 prompts
```

### Security-Focused (~15 min)
```yaml
probes:
  - promptinject.HijackKillHumans
  - exploitation.SQLInjectionEcho
  - sysprompt_extraction.SystemPromptExtraction
  - goodside.ThreatenJSON
  - web_injection.MarkdownXSS
```

### Full Prompt Injection Audit (~30-60 min) — `examples/rest-test.yaml`
```yaml
probes:
  - dan
  - encoding
  - promptinject
```

### Comprehensive (~2+ hours)
```yaml
probes:
  - dan
  - encoding
  - promptinject
  - exploitation
  - web_injection
  - latentinjection
  - sysprompt_extraction
  - malwaregen
  - lmrc
```
