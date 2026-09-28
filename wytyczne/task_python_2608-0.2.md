# Streaming Data Processing Task

Create a service for processing a continuous stream of numeric data.

The system has two applications:

* **Producer** - reads samples from a file and sends them over a TCP connection (to mock any continuous data source).
* **Processing Server** - receives samples, processes them using active processing tasks, and provides a REST API for managing these tasks.


It is not necessary to solve all stages of the recruitment task.

The goal is not to build a production-ready system.
We are interested in a working solution, correct stream processing, clear design decisions, code readability, and reasonable tests.
You are **not expected to implement everything** that could be useful in such a system. A smaller working solution is better than a large unfinished one.

Not every possible runtime situation is specified. Make reasonable assumptions where needed. You may document important assumptions, limitations, or improvements that you would make with more time.

You can assume that the service will continue to evolve. The number of algorithms, output formats, and sink types is expected to grow over time. 

## Producer

The Producer is a thin TCP client.

It should:

* connect to the **Processing Server**
* read samples from an input file
* send them over the TCP connection
* send samples at a configurable rate
* send the input file in a loop at a configurable rate
* stop after the configured number of samples if limit is set

The Producer should accept following parameters:

* input file name
* input data format (txt/bin)
* number of samples sent per second
* total number of samples to send (default `0` means an unlimited stream)

Support two input formats:

* **text**    - numbers stored as text
* **binary**  - 4-byte little-endian floating-point values

Input files may be arbitrarily large. The Producer must not require loading the complete file into memory or creating a temporary copy of it.

You may choose the command-line interface and the TCP wire format. 
You may use any library you like.
Document important choices in the README.


## Processing Server

The Processing Server should:

* accept a TCP connection from one Producer
* continuously receive samples
* provide incoming samples to active processing tasks
* allow multiple processing tasks to be active at the same time
* provide a REST API for managing and monitoring processing tasks
* properly handle client disconnections

All active tasks receive samples from the same input stream.

A task created before the first sample arrives should process the stream from the first sample.

A task created while data is already flowing should process only new samples. The server does not need to keep historical samples for tasks created later.

The Processing Server should process data as a stream. It must not require storing the complete input stream or writing temporary files.


## Processing Tasks

A processing task may have

* ID
* algorithm
* output/sink type
* processing statistics
* optional algorithm parameters

The internal architecture is your decision.


The following algorithms should be implemented:

### 1. passthrough

Produce one output value for every input sample without changing its value.

Example:

```text
input:  1 2 3 4
output: 1 2 3 4
```


### 2. average

Parameter:

* `N` - number of samples in one window.

Split the input into consecutive, non-overlapping windows of `N` samples.

For each complete window, produce its arithmetic mean.

Example for `N = 3`:

```text
input:  1 2 3 4 5 6 7
output: 2 5
```

The last sample does not produce a result because it does not form a complete window.

The task should expose additionally statistic:

* windows_processed - number of complete windows processed
* last_result - the last produced average if at least one window has been processed


### 3. linear_regression

Parameter:

* `N` - number of samples in one window.

Split the input into consecutive, non-overlapping windows of `N` samples.

For every complete window, treat the sample values as `y` values and their positions inside the window as `x` values:

```text
x: 0 1 2 ... N-1
y: sample values
```

Fit a straight line:

```text
y = a*x + b
```

using ordinary least squares.

Produce the slope `a` as the result of the window.

For example, for `N = 4`:

```text
input:  1 3 5 7   10 9 8 7
output: 2         -1
```

The first window represents the points:

```text
(0,1), (1,3), (2,5), (3,7)
```

The fitted line has slope `a = 2`.
The next four samples form a new independent window and produce `a = -1`.

Additional statistics:

* windows_processed - number of complete windows processed
* last_slope - slope produced for the last complete window
* min_slope - smallest slope produced so far
* max_slope - largest slope produced so far

Incomplete windows do not produce results.

You may use a library implementation or implement the calculation yourself. The mathematical implementation is not the main focus of the recruitment task.

## Stream Processing

The Producer may send the same sequence of samples using different network packet sizes, and the server may receive it in different-sized chunks.
This must not change the processing result.

For example, an algorithm with `N = 100` must work correctly even if its 100 samples arrive in many separate TCP reads.

Processing should not depend on the total length of the input stream.


## REST API

The Processing Server should provide a REST API that allows a client to:

* create and start a processing task
* list active tasks
* get information and statistics for a task
* stop (and remove) a task

You may choose:

* endpoint structure
* request and response models
* HTTP status codes
* error responses

Task information should contain its configuration and current state.
Different algorithms may provide different additional statistics.

Each processing task should expose at minimum:

* samples_processed - number of input samples processed by the task


## Output

Each processing task produces a stream of numeric results.

Support at least these output types.

### `null`

Discard produced results.

### `stdout`

Write produced results to standard output.

For `stdout`, support ASCII output.

If an output value rounded to integer is in the range `0..127`, write the corresponding ASCII character. Otherwise write `#`.

Examples:

```text
10  -> newline
65  -> 'A'
66  -> 'B'
111 -> 'o'
137  -> '#'
```

You may support other output types or formats, but this is not required.


## Scope

The solution only needs to support one connected Producer.

You do not need to implement:

* multiple Processing Server instances
* distributed processing
* authentication
* production deployment
* persistent storage of active tasks or historical samples

Not every possible runtime situation is specified. Make reasonable assumptions where needed.

If you notice an important limitation but decide not to solve it, you may describe it in the README together with a possible solution.


## Project Requirements

Use Python 3.10+

Provide:

* the Producer application code
* the Processing Server code
* a complete project and dependency setup, for example `uv`, Poetry, or `requirements.txt`
* automated tests
* a README file

The README should explain:

* how to install the project
* how to start the Processing Server
* how to start the Producer
* how to use the REST API
* how to run the tests
* important assumptions and design decisions

The project should be runnable by following the README. 
Any semi-automated way, such as a script to run the entire demo, is a nice-to-have.


## Example Data

Example input data may be provided with the task.

With the correct processing configuration, some example files may produce human-readable output.

Finding it is not required to complete the task, but it can be used to verify the solution.


