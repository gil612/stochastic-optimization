"""
Asset selling model class
Adapted from code by Donghun Lee (c) 2018

"""
from collections import namedtuple
import numpy as np


class AssetSellingModel:
    """
    Base class for model
    """

    def __init__(
        self,
        state_variable,
        decision_variable,
        state_0,
        exog_0,
        T=10,
        seed=42,
    ):
        """
        Initializes the model

        :param state_variable: list(str) - state variable dimension names
        :param decision_variable: list(str) - decision variable dimension names
        :param state_0: dict - needs to contain at least the information to populate
                                initial state using state_names
        :param exog_info_fn: function - calculates relevant exogenous information
        :param transition_fn: function - takes in decision variables and exogenous
                                information to describe how the state evolves
        :param objective_fn: function - calculates contribution at time t
        :param seed: int - seed for random number generator
        """

        self.initial_args = {
            "seed": seed,
            "T": T,
            "exog_params": exog_0,
        }
        exog_params = self.initial_args["exog_params"]
        biasdf = exog_params["biasdf"]
        biasdf = biasdf.cumsum(axis=1)
        self.initial_args["exog_params"].update({"biasdf": biasdf})

        self.prng = np.random.default_rng(seed)
        self.initial_state = state_0
        self.state_variable = state_variable
        self.decision_variable = decision_variable
        self.State = namedtuple("State", state_variable)
        self.state = self.build_state(state_0)
        self.Decision = namedtuple("Decision", decision_variable)
        self.objective = 0.0

    def build_state(self, info):
        """
        this function gives a state containing all the state information needed

        :param info: dict - contains all state information
        :return: namedtuple - a state object
        """
        return self.State(*[info[k] for k in self.state_variable])

    def build_decision(self, info):
        """
        this function gives a decision

        :param info: dict - contains all decision info
        :return: namedtuple - a decision object
        """
        return self.Decision(*[info[k] for k in self.decision_variable])

    def exog_info_fn(self):
        """
        Triggers one timestep t->t+1 of the exogenous information,
        usually dependent on a random process
        (in the case of the asset selling model, it is the change in price)

        :return: dict - updated price
        """
        # Assumption: change in price is normally distributed with mean bias and var 2
        exog_params = self.initial_args["exog_params"]

        biasdf = exog_params["biasdf"].T
        biasprob = biasdf[self.state.bias]

        coin = self.prng.uniform()
        if coin < biasprob["Up"]:
            new_bias = "Up"
            bias = exog_params["UpStep"]
        elif coin >= biasprob["Up"] and coin < biasprob["Neutral"]:
            new_bias = "Neutral"
            bias = 0
        else:
            new_bias = "Down"
            bias = exog_params["DownStep"]

        price_delta = self.prng.normal(bias, exog_params["Variance"])
        updated_price = self.state.price + price_delta
        # we account for the fact that asset prices cannot be negative by setting
        # the new price as 0 whenever therandom process gives us a negative price
        new_price = 0.0 if updated_price < 0.0 else updated_price

        return {
            "price": new_price,
            "bias": new_bias,
        }

    def transition_fn(self, decision, exog_info):
        """
        Takes the decision and exogenous information W_t+1 to update the state

        :param decision: namedtuple - contains all decision info
        :param exog_info: any exogenous info (in this asset selling model,
               the exogenous info does not factor into the transition function)
        :return: dict - updated resource
        """
        alpha = 0.7
        new_resource = 0 if decision.sell == 1 else self.state.resource
        new_price_smoothed = (
            1 - alpha
        ) * self.state.price_smoothed + alpha * exog_info["price"]

        return {"resource": new_resource, "price_smoothed": new_price_smoothed}

    def objective_fn(self, decision, exog_info):
        """
        Calculates the contribution, which depends on the decision and the price

        :param decision: namedtuple - contains all decision info
        :param exog_info: any exogenous info (in this asset selling model,
               the exogenous info does not factor into the objective function)
        :return: float - calculated contribution
        """
        sell_size = 1 if decision.sell == 1 and self.state.resource != 0 else 0
        obj_part = self.state.price * sell_size
        return obj_part

    def step(self, decision):
        """
        this function steps the process forward by one time increment by updating
        1. the exogenous information
        2. the sum of the contributions
        3. the state variable

        :param decision: namedtuple - contains all decision info
        :return: current state values
        """
        exog_info = self.exog_info_fn()
        self.objective += self.objective_fn(decision, exog_info)
        exog_info.update(self.transition_fn(decision, exog_info))
        self.state = self.build_state(exog_info)

        return self.state
