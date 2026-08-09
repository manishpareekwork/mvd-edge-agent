# Edge Storage

Reserved for offline buffering and retry storage.

The first POC version sends RFID events directly to the cloud API. A future
version should persist unsent events locally so short network outages do not
drop ENTER or EXIT events.
