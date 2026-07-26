use strict;
use warnings;
use lib 'lib';
use MyModule::Greeter;
use MyModule::Circle;

my $greeter = MyModule::Greeter->new(name => "CGC");
print $greeter->greet() . "\n";

my $circle = MyModule::Circle->new(radius => 5);
print "Circle area: " . $circle->area() . "\n";
