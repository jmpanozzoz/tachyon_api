from datetime import datetime

from tachyon_api import Tachyon
from tachyon_api.params import Body, Path, Query
from tachyon_api.di import Depends
from tachyon_api.responses import (
    success_response,
    error_response,
    not_found_response,
    conflict_response,
    validation_error_response,
    JSONResponse,
)

# Import our models and services
from example.models.item import Item
from example.services.item import ItemService

# Create app instance
app = Tachyon()


# === Basic Examples ===


@app.get("/")
async def root():
    """
    Welcome endpoint - demonstrates basic success response

    Shows how to use success_response() with custom data and message
    """
    return success_response(
        data={
            "message": "Welcome to Tachyon API Training Server!",
            "features": [
                "Dependency Injection",
                "Type Validation",
                "OpenAPI Documentation",
                "Structured Responses",
            ],
            "endpoints": {"docs": "/docs", "redoc": "/redoc", "health": "/health"},
        },
        message="Server is running successfully",
    )


@app.get("/health")
async def health_check():
    """
    Health check endpoint - simple success response

    Demonstrates minimal success response for monitoring
    """
    now = datetime.now()
    # Return current time as part of health check
    return success_response(
        data={"status": "healthy", "timestamp": now.isoformat()},
        message="Service is healthy",
    )


# === Error Handling Examples ===


@app.get("/examples/success")
async def example_success():
    """Example of structured success response"""
    return success_response(
        data={"operation": "completed", "result_id": 12345},
        message="Operation completed successfully",
    )


@app.get("/examples/error")
async def example_error():
    """Example of basic error response"""
    return error_response("This is an example error message", code="EXAMPLE_ERROR")


@app.get("/examples/not-found")
async def example_not_found():
    """Example of not found response"""
    return not_found_response("The requested example resource was not found")


@app.get("/examples/conflict")
async def example_conflict():
    """Example of conflict response"""
    return conflict_response("Example resource already exists with this identifier")


@app.get("/examples/validation-error")
async def example_validation_error():
    """Example of validation error with field details"""
    field_errors = {
        "name": ["Name is required", "Name must be at least 3 characters"],
        "email": ["Invalid email format"],
        "age": ["Must be a positive number"],
    }
    return validation_error_response("Input validation failed", errors=field_errors)


# === CRUD Examples with Items ===


@app.get("/items")
async def list_items(
    limit: int = Query(default=10, description="Maximum number of items to return"),
    search: str = Query(default=None, description="Search term to filter items"),
    item_service: ItemService = Depends(),
):
    """
    List all items with optional filtering

    Demonstrates:
    - Query parameters with defaults
    - Dependency injection
    - Structured success response with metadata
    """
    try:
        items = item_service.list_items()

        # Apply search filter if provided
        if search:
            items = [item for item in items if search.lower() in item.name.lower()]

        # Apply limit
        items = items[:limit]

        # Convert to dict format for JSON response
        items_data = [
            {"id": item.id, "name": item.name, "description": item.description}
            for item in items
        ]

        return success_response(
            data={
                "items": items_data,
                "count": len(items_data),
                "filters": {"limit": limit, "search": search},
            },
            message=f"Retrieved {len(items_data)} items successfully",
        )

    except Exception as e:
        return error_response(f"Failed to retrieve items: {str(e)}")


@app.get("/items/{item_id}")
async def get_item(
    item_id: int = Path(description="Unique identifier of the item"),
    item_service: ItemService = Depends(),
):
    """
    Get a specific item by ID

    Demonstrates:
    - Path parameters with validation
    - Conditional responses (success vs not found)
    - Clean error handling
    """
    try:
        item = item_service.get_item(item_id)

        if not item:
            return not_found_response(f"Item with ID {item_id} was not found")

        return success_response(
            data={"id": item.id, "name": item.name, "description": item.description},
            message="Item retrieved successfully",
        )

    except ValueError as e:
        return error_response(f"Invalid item ID: {str(e)}", code="INVALID_ID")
    except Exception as e:
        return error_response(f"Failed to retrieve item: {str(e)}")


@app.post("/items")
async def create_item(
    item: Item = Body(description="Item data to create"),
    item_service: ItemService = Depends(),
):
    """
    Create a new item

    Demonstrates:
    - Body parameter validation with Struct models
    - Service layer error handling
    - Different response types based on operation result
    """
    try:
        created_item, error = item_service.create_item(item)

        if error:
            # Handle different types of service errors
            if "already exists" in error.lower():
                return conflict_response(error)
            elif "validation" in error.lower():
                return validation_error_response(error)
            else:
                return error_response(error, code="CREATION_FAILED")

        return success_response(
            data={
                "id": created_item.id,
                "name": created_item.name,
                "description": created_item.description,
            },
            message="Item created successfully",
            status_code=201,  # Created status
        )

    except Exception as e:
        return error_response(f"Unexpected error creating item: {str(e)}")


@app.put("/items/{item_id}")
async def update_item(
    item_id: int = Path(description="ID of item to update"),
    item_data: Item = Body(description="Updated item data"),
    item_service: ItemService = Depends(),
):
    """
    Update an existing item

    Demonstrates:
    - Combining path and body parameters
    - Update operations with proper responses
    """
    try:
        # Check if item exists first
        existing_item = item_service.get_item(item_id)
        if not existing_item:
            return not_found_response(f"Item with ID {item_id} not found")

        # Use the service's update method
        updated_item, error = item_service.update_item(item_id, item_data)

        if error:
            return error_response(error, code="UPDATE_FAILED")

        return success_response(
            data={
                "id": updated_item.id,
                "name": updated_item.name,
                "description": updated_item.description,
                "updated": True,
            },
            message="Item updated successfully",
        )

    except Exception as e:
        return error_response(f"Failed to update item: {str(e)}")


@app.delete("/items/{item_id}")
async def delete_item(
    item_id: int = Path(description="ID of item to delete"),
    item_service: ItemService = Depends(),
):
    """
    Delete an item

    Demonstrates:
    - DELETE operations
    - Success response without data payload
    """
    try:
        success, error = item_service.delete_item(item_id)

        if error:
            if "not found" in error.lower():
                return not_found_response(error)
            return error_response(error, code="DELETE_FAILED")

        return success_response(
            data={"deleted_id": item_id}, message=f"Item {item_id} deleted successfully"
        )

    except Exception as e:
        return error_response(f"Failed to delete item: {str(e)}")


# === Advanced Examples ===


@app.get("/examples/mixed-response")
async def mixed_response_example():
    """
    Example showing how to mix structured responses with regular JSON

    Sometimes you might want to return raw JSON for specific use cases
    """
    use_structured = True  # This could come from a query parameter

    if use_structured:
        return success_response(
            data={"type": "structured", "format": "tachyon"},
            message="Using structured response format",
        )
    else:
        # Return raw JSON using Starlette's JSONResponse directly
        return JSONResponse(
            {"type": "raw", "format": "standard", "note": "This is a raw JSON response"}
        )


@app.get("/examples/custom-headers")
async def custom_headers_example():
    """
    Example showing custom headers in responses
    """
    return JSONResponse(
        {
            "success": True,
            "message": "Response with custom headers",
            "data": {"example": "data"},
        },
        headers={
            "X-Custom-Header": "training-example",
            "X-API-Version": "1.0",
            "X-Response-Time": "fast",
        },
    )
