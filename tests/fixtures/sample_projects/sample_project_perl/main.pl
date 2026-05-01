#!/usr/bin/perl

use strict;
use warnings;
use lib 'lib';
use MyModule::Greeter;

sub main {
    my $greeter = MyModule::Greeter->new(greeting => "Welcome");
    $greeter->greet("Developer");
}

main();
