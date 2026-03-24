# Examples for Background Queue Client

## Basic Usage

Here's a basic example of how to use the background queue client:

```python
from background_queue_client import BackgroundQueueClient

# Initialize the client
client = BackgroundQueueClient(api_key='YOUR_API_KEY')

# Add a task to the queue
response = client.add_task(task_data={'task': 'send_email', 'to': 'user@example.com'})
print('Task added:', response)

# Fetch task status
status = client.get_task_status(task_id=response['task_id'])
print('Task Status:', status)
```

## Handling Task Results

After adding a task, you can wait for its result:

```python
import time

# Wait for the task to complete
while True:
    status = client.get_task_status(task_id=response['task_id'])
    if status['status'] == 'completed':
        print('Task result:', status['result'])
        break
    elif status['status'] == 'failed':
        print('Task failed:', status['error'])
        break
    time.sleep(5)  # Wait before checking again
```

## Error Handling

Make sure to handle potential errors when using the queue:

```python
try:
    response = client.add_task(task_data={'task': 'generate_report'})
except Exception as e:
    print('Failed to add task:', e)
```

## Conclusion

This provides a basic overview of using the background queue client. Refer to the documentation for more advanced features and settings.