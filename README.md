# Using LLM Agent to respond to grievances on Twitter
- Fine tuning LLM on customer support and airline twitter customer grievances data to respond to any customer grievances on twitter using kafka and spark
- We use LLM to generate a new generation of Business Process Management suites

## Key Technologies for LLM
- Kafka Producer for tweet streaming
- Tweepy for twitter api
- LLM Chains with OpenAI Model
- Custom Output Parsers to validate steps
- ReACT Prompt Engineering Technique
- Retrieval Augmented Generation
- Speech to Text with Whisper AI
- Database and API LLM Integrations

## Business Process Management
A BPM or Business Process management can be represented as a Directed Acyclic Graph (DAG), as we go from an input to an output.
In this case we go from Customer raising a complaint or greivance and the output of the same would be either a ticket raised or 
directing a customer to getting a call from a human agent, etc.

## Directed Acyclic Graph (DAG)
We use a Directed Acyclic graph concept to design our customer support chatbot. A DAG is used to move from one state to the next

### Nodes
- They are conversational checkpoints where user and agent interact
### Edges
- Serve as Validation gateway. They decide if the user can advance to the next step


