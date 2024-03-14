from kafka import KafkaProducer
from streamlit import StreamlitApp, text_input

from MLPipeline.References import References

class Engine_kafka(References):

    def __init__(self):
        """ Setup Kafka Producer"""
        self.producer = KafkaProducer(bootstrap_servers=self.BOOTSTRAP_SERVER)  # Same port as your Kafka server

    def stream_text_to_kafka(self, text_data):
        """Stream Text Data to Kafka"""
        # Assuming text_data is a string that you want to send to Kafka
        self.producer.send('your_topic_name', value=text_data.encode('utf-8'))

# Assuming you have a StreamlitApp class or module that represents your Streamlit app
class YourStreamlitApp(StreamlitApp):

    def __init__(self, engine):
        self.engine = engine

    def run(self):
        # Your Streamlit app logic
        text_data = text_input('Enter text:')
        if text_data:
            self.engine.stream_text_to_kafka(text_data)

# Create an instance of the Engine_kafka class
e = Engine_kafka()

# Create an instance of YourStreamlitApp, passing the engine
streamlit_app = YourStreamlitApp(e)

# Run the Streamlit app
streamlit_app.run()