## Tool Implementation and Definition

First we implement the function for the `get_weather` tool:
```python
def get_weather( location : str, unit : str | None = None) -> str :
    # ... 
    # get temperature with units as string
    # ...
    return temperature_with_units_as_string
```

Then we define its **input schema** in `get_weather.json`.
```json
{
"name"         : "get_weather",
"description"  : "Get the current weather in a given location",
"input_schema" :
    {
    "type"       : "object",
    "properties" :
    {
        "location" :
        {
            "type"        : "string",
            "description" : "The city and state, e.g. San Francisco, CA"
        },
        "unit" :
        {
            "type"        : "string",
            "enum"        : [ "celsius", "fahrenheit"],
            "description" : "The unit of temperature, either 'celsius' or 'fahrenheit'"
        }
    },
    "required"             : ["location"],
    "additionalProperties" : false
}
}
```

### Special Case: No Arguments

Suppose you want to implement a tool that does not take any arguments, like one for picking a random number.
```python
import random

def random_01() -> str :
    return str(random.random())
```

Then it input schema would look like the one shown below.
```json
{
"name"         : "random_01",
"description"  : "Pick a random number between 0 and 1",
"input_schema" :
    {
    "type": "object",
    "properties": {},
    "additionalProperties": false
    }
}
```

## Tool Use Request and Result

We prompt the agent while offering it the possibility of tool use.

```python
import anthropic
import json

client   = anthropic.Anthropic()
msg_user = { "role"    : "user",
             "content" : [
                { "type" : "text",
                  "text" : "What's the weather like in San Francisco?" } ] }
response = client.messages.create(
    model    = "claude-something-something",
    messages = [ msg_user ],
    tools    = [ json.load(open("get_weather.json")) ],
    max_tokens = 1024
    )
```

The agent responds with two content blocks: one for text and another for tool use.

```json
{
"role": "assistant",
"content":
    [
        {
        "type" : "text",
        "text" : "I need to call the get_weather function, and the user wants SF, which is likely San Francisco, CA."
        },
        {
        "type"  : "tool_use",
        "id"    : "toolu_01A09q90qw90lq917835lq9",
        "name"  : "get_weather",
        "input" : { "location" : "San Francisco, CA", "unit" : "celsius" }
        }
    ]
}
```

First we collect the agent message. Next, we collect the **tool use content block** data, evaluate the function, and prepare the tool result message.
```python
# Collect agent message text
msg_agent = { "role"    : "assistant",
              "content" : response.content }

# Collect tool use content block data
tucb        = response.content[1]
tool_use_id = tucb.id
# Evaluate function
tool_result = get_weather( tucb.input.location, tucb.input.unit)
# Prepare tool result message
msg_tool = {
    "role": "user",
    "content": [ { "type"        : "tool_result",
                   "tool_use_id" : tool_use_id,
                   "content"     : tool_result,
                   "is_error"    : False } ] }
```

Finally, we re-prompt the agent, this time including the tool result.
```python
response = client.messages.create(
    model    = "claude-something-something",
    messages = [ msg_user, msg_agent, msg_tool ],
    tools    = [ json.load(open("get_weather.json")) ],
    max_tokens = 1024
    )
```

Ideally, we should get an output somewhat like this.
```json
{
"role": "assistant",
"content":
    [
        {
        "type" : "text",
        "text" : "The weather is 24 degrees Celsius"
        }
    ]
}
```
