- [ ] LLama 3.2 3b is multimodal. Use that functionality in parallel threads to figure out meaning. Look into: https://github.com/ollama/ollama/blob/main/docs/api.md#request-4 and read https://x.com/AIatMeta/status/1839018077595541855 and https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/
- [ ] End to end approach, ask /cmd navigate to "https://ai.meta.com/blog/" and summarize the most important content. 

- [ ] Add --headless to toggle headless browsers.

- [ ] Break project in modules

- [ ] fix command history broken

- [ ] make edit mode actually run your prompts to modify the code ONLY in its own chat thread.
- [ ] save written scripts to generated_scripts/ with docs and info about why they were created.
        - [ ] classify in tmp, failed, and the $root directory which includes anything actually functional that maybe should get productionalized (auto ut's etc)
- [ ] allow retries on the runs, with max_depth (configurable with arg --max-depth=3)

- [ ] move to poetry

- [ ] Implement proper code extraction and proper code imports on generated code blocks. Perform code compilation/validation stages before committing to final code approach.

- [ ] Use an in memory json to remember user use-cases over different runs. Design to auto populate the system prompts and improve code accuracy.

- [ ] Use in memory documentation and code examples for a topic using an in memory json