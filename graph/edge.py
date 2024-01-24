import abc
from typing import Generic, TypeVar, Optional, Union, List

from langchain.schema import OutputParserException
from pydantic import BaseModel

from data.chat import Role
from data.graph import EdgeOutput, MessageOutput

EdgeInput = TypeVar("EdgeInput")
ResultsType = TypeVar("ResultsType")

class BaseEdge(abc.ABC, Generic[EdgeInput, ResultsType]):
    def __init__(self, model, max_retries=3, out_node=None):
        self._llm_model = model

        # If the edge fails for any reason _num_fails increses till the max tries,
        # and is reset to zero for posterity
        self._num_fails = 0

        # max number of tries that are acceptable
        self._max_retries = max_retries

        # the node at the end of the edge
        self._out_node = out_node

    # concerete implementation of this function must be present in the subclass
    @abc.abstractmethod
    def _get_message_output(
        self, msg_input: Union[str, BaseModel]
    ) -> Optional[List[MessageOutput]]:
        pass

    @abc.abstractmethod
    def check(self, model_output: str) -> bool:
        pass

    @abc.abstractmethod
    def _parse(self, model_input: EdgeInput) -> ResultsType:
        pass

    def _get_edge_output(
            self, should_continue: bool, result: Optional[ResultsType]
    ) -> EdgeOutput:
        message_output = self._get_message_output(result)
        return EdgeOutput(
            should_continue=should_continue,
            result=result,
            num_fails=self._num_fails,
            next_node=self._out_node,
            message_output=message_output
        )
    
    def execute(self, user_input: EdgeInput):
        """Executes the entire edge
        returns a dictionary:
        {
        continue: bool, weather or not should continue to next
        result: parse_class, the parsed result, if applicable
        num_fails: int the number of failed attempts
        continue_to: Node the node the edge continues to
        }
        """
        try:
            self._num_fails = 0
            return self._get_edge_output(
                should_continue=True, result=self._parse(user_input)
            )
        except OutputParserException as parsing_exception:
            # if there is some error in parsing then we use the 
            # retry or correction parser 
            self._num_fails += 1
            if self._num_fails >= self._max_retries:
                return self._get_edge_output(
                    should_continue =True,
                    result=MessageOutput(
                        parsing_exception.llm_output, role=Role.SYSTEM
                    ),
                )
            return self._get_edge_output(
                should_continue=False,
                result=MessageOutput(parsing_exception.llm_output, role=Role.SYSTEM)
            )
