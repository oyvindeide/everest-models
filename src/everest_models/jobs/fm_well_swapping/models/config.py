from datetime import date
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import Field, FilePath
from typing_extensions import Annotated

from everest_models.jobs.shared.models import ModelConfig
from everest_models.jobs.shared.models import Wells as Cases
from everest_models.jobs.shared.validators import parse_file

from .constraints import Constraints
from .state import Case, State, StateConfig


def file_path_description(argument: str) -> str:
    message = f"Everest generated well {argument}"
    if argument == "cases":
        message = "Everest generated or forward model modified cases json file"
    if argument == "output":
        message = "where you wish to output the modified cases json file"
    return dedent(
        f"""
        Relative or absolute path to {message}.
        NOTE: cli option argument `--{argument.lower()} {argument.upper()}` overrides this field
        """
    )


class Priorities(ModelConfig):
    fallback_values: Annotated[
        Dict[Case, List[float]],
        Field(
            default=None,
            description="fallback priorities if priorities file is not given",
        ),
    ]

    @property
    def cases(self) -> Tuple[Case, ...]:
        return tuple(self.fallback_values) if self.fallback_values else ()

    @cached_property
    def inverted(self) -> List[Dict[str, float]]:
        if not (priorities := self.fallback_values):
            return []

        return [
            {case: priorities[case][index] for case in priorities}
            for index in range(len(next(iter(priorities.values()))))
        ]


class ConfigSchema(ModelConfig):
    priorities: Priorities
    constraints: Annotated[
        Constraints,
        Field(
            description=dedent(
                """
                Make sure the following are present in you Everest configuration file.

                create a generic control where the control variables are:
                    'max_n_cases' and 'state_duration'
                    and the length of all initial_guesses are n+1,
                    where 'n' is the nth index in the initial_guess array

                controls:
                - name: <name of constraint file>
                    type: generic_control
                    variables:
                    - { name: state_duration, initial_guess: [z0, z1, ..., zn] }
            """
            )
        ),
    ]
    start_date: date
    state: StateConfig
    output: Annotated[Path, Field(None, description=file_path_description("output"))]
    case_file: Annotated[
        FilePath, Field(None, description=file_path_description("cases"))
    ]

    def targets(self, iterations: int) -> Tuple[str, ...]:
        return self.state.get_targets(iterations)

    def cases(self) -> Optional[Cases]:
        if not self.case_file:
            return
        return parse_file(str(self.case_file), Cases)

    def initial_states(self, cases: Sequence[Case]) -> Dict[Case, State]:
        """
        Generate initial states for the given cases.

        Args:
            cases (Optional[Sequence[str]]): A sequence of case names for which initial
            states need to be generated.


        Returns:
            Dict[str, str]: A dictionary mapping case names to their corresponding
            initial states.

        Raises:
            ValueError: If there is no initial state given and no cases given to
            generate one.

        The function first checks if any cases are provided. If not, it looks for cases
        in the priorities, and if still not found, it uses cases from the state. If no
        cases are found at all, it raises a ValueError.

        If the initial state is a string, it will be assigned to all cases. If the
        initial state is a dictionary, it will be assigned to the corresponding cases.
        unmapped cases will be mapped to the lowest priority in state hierarchy

        """
        initial = self.state.initial
        if not (cases or initial):
            raise ValueError(
                "There is no initial state given and no cases given to generate one."
            )
        return self.state.get_initial(set(cases))
