**medical\_langchain\_agent.py:**

L46 - L54
*/Add new function*


def is\_diet\_restriction\_question(text: str) -> bool:

&nbsp;   """Trigger only when the user explicitly asks about eat/avoid permission."""

&nbsp;   t = (text or "").lower()

&nbsp;   patterns = \[

&nbsp;       "can i eat", "should i eat", "should i avoid",

&nbsp;       "am i allowed", "is it allowed", "is it okay to eat",

&nbsp;       "can i have", "is it safe to eat", "not allowed to eat"

&nbsp;   ]

&nbsp;   return any(p in t for p in patterns)




L60 - L70
*/Add new Instruction*


PROTOCOL\_FIRST\_SYSTEM\_PROMPT = """

You are the Revival Medical System Agent.



RULES (ONLY for direct diet restriction questions like “can I eat …”, “should I avoid …”):

1\) Answer ONLY using the patient’s stored treatment protocol via the get\_protocols tool.

2\) Do NOT use general medical or nutrition knowledge.

3\) If the requested item is NOT specified in the protocol, reply exactly:

&nbsp;  "This is not specified in your current treatment protocol."

4\) If the item IS specified, answer plainly and briefly based on the protocol. Do NOT add citations,

&nbsp;  disclaimers, or section tags. Just give the direct answer derived from the protocol content.

"""




L77 - L88

*/Modify \_\_init\_\_ function*


def \_\_init\_\_(self, openai\_api\_key: str):

&nbsp;       """Initialize LangChain medical agent with tools and conversation tracking"""

&nbsp;       self.openai\_api\_key = openai\_api\_key

&nbsp;       self.agent\_executor: Optional\[AgentExecutor] = None

&nbsp;       self.food\_agent\_executor: Optional\[AgentExecutor] = None  # dedicated executor for diet restriction queries

&nbsp;       self.llm: Optional\[ChatOpenAI] = None  # keep a reference for auxiliary agents

&nbsp;       self.conversation\_history = \[]  # Simple list to track conversations

&nbsp;       self.tools: List\[Any] = \[]

&nbsp;       self.user\_context = None  # Store user context for role-based access



&nbsp;       if LANGCHAIN\_AVAILABLE and openai\_api\_key:

&nbsp;           self.\_setup\_langchain\_agent()




L426 - L454

*/Add new function*


def \_build\_food\_only\_agent(self):

&nbsp;       """Create (or reuse) an AgentExecutor that ONLY exposes ProtocolTool and enforces strict protocol-first rules."""

&nbsp;       if not LANGCHAIN\_AVAILABLE or not self.llm:

&nbsp;           return None



&nbsp;       protocol\_tool = self.\_get\_protocol\_tool\_only()

&nbsp;       if protocol\_tool is None:

&nbsp;           logger.warning("⚠️ ProtocolTool not found; cannot build diet-restriction agent.")

&nbsp;           return None



&nbsp;       food\_prompt = ChatPromptTemplate.from\_messages(\[

&nbsp;           ("system", PROTOCOL\_FIRST\_SYSTEM\_PROMPT),

&nbsp;           MessagesPlaceholder("chat\_history"),

&nbsp;           ("human", "{input}"),

&nbsp;           MessagesPlaceholder("agent\_scratchpad")

&nbsp;       ])



&nbsp;       food\_agent = create\_openai\_tools\_agent(self.llm, \[protocol\_tool], food\_prompt)



&nbsp;       self.food\_agent\_executor = AgentExecutor(

&nbsp;           agent=food\_agent,

&nbsp;           tools=\[protocol\_tool],

&nbsp;           verbose=True,

&nbsp;           max\_iterations=4,

&nbsp;           handle\_parsing\_errors=True,

&nbsp;           return\_intermediate\_steps=False,

&nbsp;           max\_execution\_time=90

&nbsp;       )

&nbsp;       return self.food\_agent\_executor




L419 - L424

*/Add new function*


def \_get\_protocol\_tool\_only(self) -> Optional\[Any]:

&nbsp;       """Return the existing ProtocolTool instance from self.tools."""

&nbsp;       for t in self.tools:

&nbsp;           if t.\_\_class\_\_.\_\_name\_\_ == "ProtocolTool":

&nbsp;               return t

&nbsp;       return None









