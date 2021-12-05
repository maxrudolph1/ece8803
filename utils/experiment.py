import numpy as np
from utils.thompson import ThompsonSampling
class Experiment:
    def __init__(self, num_arms=None, true_funny=None, true_unfunny=None, true_somewhat=None,
                 prior_succ=None, prior_fail=None, dist='beta', trials=1000):
        self.prior_succ = prior_succ
        self.prior_fail = prior_fail
        self.num_arms = num_arms
        self.true_funny = true_funny
        self.true_unfunny = true_unfunny
        self.true_somewhat = true_somewhat
        self.true_means = (self.true_funny + self.true_somewhat * 0.5 ) / (self.true_funny + self.true_somewhat + self.true_unfunny) 
        self.dist = dist
        self.trials=trials
        self.optimal_arm = np.argmax(self.true_means)
        self.thomp = ThompsonSampling(self.num_arms, self.prior_succ, self.prior_fail, dist=self.dist)

    def sample_reward(self, arm):
        rand_num = np.random.random()
        rew = 1 if rand_num < self.true_funny[arm] else (0 if rand_num < self.true_funny[arm] + self.true_somewhat[arm] else -1)
        return rew

    def get_regret(self):
        delta = np.max(self.true_means) - self.true_means
        N = self.thomp.arm_pulled
        return np.sum(delta * N)

    def run_experiment(self):
        regret = np.zeros((self.trials,))
        for i in range(self.trials):
            arm = self.thomp.select_arm()
            rew = self.sample_reward(arm)
            if rew == 1:
                self.thomp.register_funny(arm)
            elif rew == 0:
                self.thomp.register_somewhat(arm)
            else: 
                self.thomp.register_unfunny(arm)

            regret[i] = self.get_regret()
        return {'regret': regret,
                'sample_means': self.thomp.get_sample_means(),
                'opt_arm': np.argmax(self.thomp.get_sample_means()),
                'true_opt_arm': np.argmax(self.true_means),
                'N_pulled': self.thomp.arm_pulled,
                 }

            
