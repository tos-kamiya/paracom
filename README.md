# pilcrow

**pilcrow** is a command-line tool that uses a Large Language Model (LLM) to recompose paragraphs from conversation transcripts. It detects the starting points of new paragraphs within a transcript and inserts blank lines to restructure the text into coherent paragraphs.

pilcrow was developed out of a need to improve the readability of audio transcript files. Often, conversation transcripts can be difficult to navigate because they lack proper paragraph breaks.

## Features

- **Automatic Paragraph Recomposition:** Detects conversation turn points (i.e. paragraph start lines) and restructures the transcript.
- **LLM-Powered Processing:** Uses an LLM via the ollama interface to analyze and segment long text.
- **Customizable Options:** Supports multiple detection trials, filtering out lines with specific prefixes, and verbose logging.
- **Easy Integration:** Designed to be installed and run via [pipx](https://pipxproject.github.io/pipx/).

## Installation

Before installing and using pilcrow, you must install [Ollama](https://ollama.com/) according to the instructions on the official Ollama website.

Then, you can install pilcrow directly from GitHub using `pipx`:

```bash
pipx install git+https://github.com/tos-kamiya/pilcrow
```

Alternatively, use `pip` as follows:

```bash
git clone https://github.com/tos-kamiya/pilcrow
cd pilcrow
pip install .
```

## Usage

After installation, you can run pilcrow from the command line. Here are some usage examples:

- **Basic Usage:**

  ```bash
  pilcrow input.txt
  ```

- **Using Standard Input:**

  ```bash
  cat transcript.txt | pilcrow -
  ```

- **Specifying Lines to Skip:**

  ```bash
  pilcrow input.txt --skip-line-prefix="---" --skip-line-prefix="###"
  ```

- **Multiple Detection Trials (e.g., 5 trials merged):**

  ```bash
  pilcrow input.txt --trials 5
  ```

- **Verbose Logging:**

  ```bash
  pilcrow input.txt --verbose
  ```

- **Output File Options:**

  Use `-o` to specify an output file name:
  
  ```bash
  pilcrow input.txt -o output.txt
  ```
  
  Or use `-O` to automatically generate an output file name by appending `-pilcrow` to the input file name (note: this option cannot be used when reading from standard input):
  
  ```bash
  pilcrow input.txt -O
  ```

### Command-Line Arguments/Options

- **`input_file`**  
  The input transcript file. Use `-` to read from standard input.

- **`--skip-line-prefix`**  
  Exclude lines starting with the specified prefix from detection. This option can be specified multiple times.

- **`--trials`**  
  The number of detection trials to run. The default is 1. If more than 1 is specified, the results are merged using a majority vote.

- **`--verbose`**  
  Output detailed log messages to standard error (prefixed with "Info:").

- **`-o/--output`**  
  Specify an explicit output file name.

- **`-O/--auto-output`**  
  Automatically generate an output file name based on the input file name (appends `-pilcrow`). This option is mutually exclusive with `-o` and cannot be used when reading from standard input.

## Example

An artificial developer memo created for demonstration purposes.

```bash
$ cat sample1-e.txt
Finished refactoring the notification module. It's now using the new event bus interface. Had to update a few listeners to handle the async behavior properly. Also fixed the bug where scheduled jobs were firing twice after a redeploy, turned out to be a misconfigured cron setup in the container init script. Still debating whether to drop support for the legacy XML config files. It’s a pain to maintain but one client still relies on it. Need to double-check if the metrics collector is pushing to the right Prometheus endpoint. Grafana dashboard hasn't updated since last week. Planning to review PR #214 tomorrow morning, looks straightforward but want to confirm the rollback logic. Didn't get around to testing the mobile flow yet. Probably tomorrow.

$ cat sample1-e.txt | pilcrow -

Finished refactoring the notification module.
It's now using the new event bus interface.
Had to update a few listeners to handle the async behavior properly.
Also fixed the bug where scheduled jobs were firing twice after a redeploy, turned out to be a misconfigured cron setup in the container init script.

Still debating whether to drop support for the legacy XML config files.
It’s a pain to maintain but one client still relies on it.
Need to double-check if the metrics collector is pushing to the right Prometheus endpoint.
Grafana dashboard hasn't updated since last week.

Planning to review PR #214 tomorrow morning, looks straightforward but want to confirm the rollback logic.

Didn't get around to testing the mobile flow yet.
Probably tomorrow.
```


## License

MIT
