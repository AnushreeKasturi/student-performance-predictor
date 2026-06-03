import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

# Load dataset
data = pd.read_csv("student_data.csv")

# Input features
X = data[['attendance', 'study_hours', 'internal_marks', 'assignments']]

# Output
y = data['final_score']

# Split data into training and testing
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Create ML model
model = LinearRegression()

# Train model
model.fit(X_train, y_train)
test_predictions = model.predict(X_test)

error = mean_absolute_error(y_test, test_predictions)



# Predict score
attendance = float(input("Enter attendance percentage(out of 100): "))
study_hours = float(input("Enter study hours(in a week): "))
internal_marks = float(input("Enter internal marks(out of 100): "))
assignments = float(input("Enter assignment marks(out of 100): "))

new_data = pd.DataFrame({
    'attendance': [attendance],
    'study_hours': [study_hours],
    'internal_marks': [internal_marks],
    'assignments': [assignments]
})

prediction = model.predict(new_data)
predicted_score=prediction[0]
if predicted_score >= 90:
    grade = "A"

elif predicted_score >= 80:
    grade = "B"

elif predicted_score >= 70:
    grade = "C"

else:
    grade = "Fail"
print("Predicted Final Score:", prediction[0])
print("Predicted Grade:", grade)
print("Mean Absolute Error:", error)
plt.scatter(data['study_hours'], data['final_score'])

plt.xlabel("Study Hours")
plt.ylabel("Final Score")

plt.title("Study Hours vs Final Score")

plt.show()
plt.scatter(data['attendance'], data['final_score'])

plt.xlabel("Attendance")
plt.ylabel("Final Score")

plt.title("Attendance vs Final Score")

plt.show()