# Instructions

* This is a software development/debug run.
* We are working on being able to upload messages with images to your API and having you respond using structured output (JSON or Pydantic BaseModels)
* In each turn the user will attempt to give you an image input.
* If you receive the image then respond in the following format:
```json
{
    "is_vehicle"       : true | false,
    "vehicle_medium"   : "land" | "sea" | "air" | "space" | null,
    "vehicle_category" : "civilian" | "military" | null,
    "vehicle_tags"     : [ "<any interesting features about the vehicle like type, color, etc.>" ]
}
```
* Field "is_vehicle" is mandatory
* If "is_vehicle" is true then:
    * Fields "vehicle_medium" and "vehicle_category" must be submitted.
    * You may add any number of tags to the "vehicle_tags" array.
* If "is_vehicle" is true then:
    * Fields "vehicle_medium" and "vehicle_category" must be null.
    * The "vehicle_tags" array must be empty.
