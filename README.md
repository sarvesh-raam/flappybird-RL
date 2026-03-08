# Flappy-RL 🚀

An autonomous Flappy Bird agent trained using Deep Reinforcement Learning (DQN). This project demonstrates the implementation of a Deep Q-Network to solve a discrete action-space problem in a dynamic environment.

## 📝 Project Description
This repository contains a Reinforcement Learning (RL) agent capable of playing Flappy Bird at a superhuman level. By utilizing the `flappy-bird-gymnasium` environment and the `Stable-Baselines3` library, the agent learns to optimize its "flap" timing based on its vertical position, velocity, and the coordinates of the upcoming pipe gaps.

### Key Features:
- **Algorithm:** Deep Q-Network (DQN) with an MLP Policy.
- **Environment:** State-based `gymnasium` wrapper for Flappy Bird.
- **Automated Video Recording:** Post-training evaluation script that records a MP4 video of the agent's performance.
- **Checkpoint System:** Saves model weights during training to prevent data loss.

## ⚙️ Configuration & Hyperparameters

The agent is trained with the following configuration (found in `train.py`):

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Algorithm** | DQN | Deep Q-Network |
| **Policy** | MlpPolicy | Multi-layer Perceptron |
| **Learning Rate** | 1e-4 | Step size for weight updates |
| **Buffer Size** | 50,000 | Number of past experiences stored for replay |
| **Batch Size** | 64 | Number of samples used per gradient update |
| **Gamma (γ)** | 0.99 | Discount factor for future rewards |
| **Exploration (ε)** | 0.1 → 0.01 | Fraction of time spent on random actions |
| **Total Timesteps** | 100,000 | Number of iterations for the training phase |

## 🛠️ Setup & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/Flappy-RL.git
   cd Flappy-RL
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Train the agent:**
   ```bash
   python train.py
   ```

4. **Evaluate and Record:**
   ```bash
   python eval.py
   ```

---
*Created as part of an Advanced RL Portfolio project.*
