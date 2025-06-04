#!/usr/bin/env python3
"""
Test script to demonstrate conversation memory in the SSE client
"""
import asyncio
import os
import sys

# Add the client directory to the path
sys.path.append(os.path.dirname(__file__))

from sse_client import MCPSSEClient


async def test_conversation_memory():
    """Test the conversation memory functionality"""
    
    client = MCPSSEClient("http://localhost:8000/sse")
    
    try:
        await client.connect_to_server()
        
        print("🧠 Testing Conversation Memory")
        print("=" * 50)
        
        # First query
        print("\n1️⃣ First query: Get weather for New York")
        response1 = await client.process_query("Get the weather forecast for New York City coordinates 40.7128, -74.0060")
        print("Response:", response1[:200] + "..." if len(response1) > 200 else response1)
        
        print(f"\nConversation length after query 1: {client.get_conversation_length()}")
        
        # Second query that references the first
        print("\n2️⃣ Second query: Follow-up question")
        response2 = await client.process_query("What about the temperature specifically?")
        print("Response:", response2[:200] + "..." if len(response2) > 200 else response2)
        
        print(f"\nConversation length after query 2: {client.get_conversation_length()}")
        
        # Third query to show it remembers context
        print("\n3️⃣ Third query: Another follow-up")
        response3 = await client.process_query("Is it going to rain there today?")
        print("Response:", response3[:200] + "..." if len(response3) > 200 else response3)
        
        print(f"\nConversation length after query 3: {client.get_conversation_length()}")
        
        # Show conversation stats
        print("\n📊 Final conversation stats:")
        client.show_conversation_stats()
        
        # Test clearing memory
        print("\n🧹 Testing memory clear...")
        client.clear_conversation_history()
        print(f"Conversation length after clear: {client.get_conversation_length()}")
        
        print("\n✅ Conversation memory test completed!")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(test_conversation_memory())
