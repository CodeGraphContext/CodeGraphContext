
import 'models.dart';
import 'utils.dart';

void main() {
  final user = User(
    id: '1',
    email: 'user@example.com',
    firstName: 'John',
    lastName: 'Doe',
  );

  print('User: ${user.getDisplayName()}');
  print('Is Valid Email: ${user.email.isValidEmail()}');

  final admin = AdminUser(
    id: '2',
    email: 'admin@system.com',
    firstName: 'Admin',
    lastName: 'Manager',
  );

  admin.grantPermission('write_access');
  print('Admin Status: ${admin.isAdmin()}');

  double originalPrice = 100.0;
  double discountedPrice = calculateDiscount(originalPrice, 15.0);
  
  print('Price: ${formatCurrency(discountedPrice)}');
  
  double r = 5.0;
  print('Area: ${MathUtils.areaOfCircle(r)}');
}

/// Async function for testing
Future<void> fetchData() async {
  print('Fetching data...');
  await Future.delayed(Duration(seconds: 1));
  print('Data fetched!');
}
