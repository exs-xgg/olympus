import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Define a simple Random Forest Classifier using PyTorch
class RandomForestClassifier(nn.Module):
    def __init__(self, n_estimators=10, max_depth=None):
        super(RandomForestClassifier, self).__init__()
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.trees = [self._create_tree() for _ in range(n_estimators)]

    def _create_tree(self):
        # Placeholder for creating a decision tree
        # In practice, you would implement a decision tree here
        return nn.Linear(10, 1)  # Dummy linear layer

    def forward(self, x):
        # Aggregate predictions from all trees
        outputs = [tree(x) for tree in self.trees]
        return torch.mean(torch.stack(outputs), dim=0)

# Generate a simple dataset
X, y = make_classification(n_samples=100, n_features=10, n_informative=5, n_classes=2, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Convert data to PyTorch tensors
tensor_x = torch.tensor(X_train, dtype=torch.float32)
tensor_y = torch.tensor(y_train, dtype=torch.float32)

dataset = torch.utils.data.TensorDataset(tensor_x, tensor_y)
train_loader = torch.utils.data.DataLoader(dataset, batch_size=10, shuffle=True)

# Initialize the model, loss function, and optimizer
model = RandomForestClassifier(n_estimators=10)
criterion = nn.BCEWithLogitsLoss()
optimizer = optim.SGD(model.parameters(), lr=0.01)

# Training loop
for epoch in range(10):  # 10 epochs
    for inputs, labels in train_loader:
        optimizer.zero_grad()
        outputs = model(inputs).squeeze()
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

    print(f'Epoch {epoch+1}, Loss: {loss.item()}')

# Evaluate the model
model.eval()
with torch.no_grad():
    test_inputs = torch.tensor(X_test, dtype=torch.float32)
    test_outputs = model(test_inputs).squeeze()
    predictions = (test_outputs > 0).int()
    accuracy = accuracy_score(y_test, predictions.numpy())
    print(f'Accuracy: {accuracy * 100:.2f}%')
