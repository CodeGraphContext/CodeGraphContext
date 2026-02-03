# PHP Sample Project

# PHP Sample Project

This folder contains a set of PHP files demonstrating major aspects/nuances of PHP programming, inspired by the Python sample_project


## Project Structure

sample_project_php/\
├── classes_objects.php\
├── database.php\
├── edgecases.php\
├── error_handling.php\
├── file_handling.php \
├── functions.php\
├── generators_iterators.php\
├── globals_superglobals.php\
├── inheritance.php\
└── interfaces_traits.php

### Features Covered

- **Functions & Callbacks**: Anonymous functions, closures, variadics  
- **Object-Oriented PHP**: Classes, inheritance, abstract classes, interfaces, traits  
- **Error Handling**: Custom exceptions, try/catch/finally  
- **File I/O**: Reading and writing files, appending content  
- **Database**: Connecting with PDO, creating tables, inserts, selects  
- **Generators & Iterators**: Yield keyword, implementing Iterator interface  
- **Edge Cases**: Type juggling, array key overwrites, null/empty comparisons  
- **Superglobals**: Accessing $_GET, $_POST, and using $GLOBALS  

### How to Run

Make sure you have PHP installed (>= 7.4 recommended) and a database if testing `database.php`.

Run individual files from the terminal:

```bash
php functions.php
php classes_objects.php
php inheritance.php
...etc
